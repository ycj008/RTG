"""
工具：GNSS/IMU 数据模拟器
在没有真实硬件的情况下，模拟 GNSS 接收机和 IMU 的 UDP 数据包，
用于系统测试和演示。

使用方式：
    python tools/simulator.py --scenario static
    python tools/simulator.py --scenario moving --speed 1.5
"""

import sys
import time
import socket
import struct
import math
import argparse
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


class GnssSimulator:
    """
    GNSS 接收机模拟器。
    生成 NMEA 格式的 GGA/RMC 语句，通过 UDP 发送。
    """

    def __init__(self, target_host: str, target_port: int, receiver_id: str):
        self.target_host = target_host
        self.target_port = target_port
        self.receiver_id = receiver_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 初始位置（深圳某港口）
        self.lat = 22.5
        self.lon = 113.9
        self.alt = 10.0
        self.heading = 90.0  # 正东
        self.speed = 0.0     # m/s

    def generate_gga(self) -> str:
        """生成 $GPGGA 语句（RTK 固定解）。"""
        # 转换为 ddmm.mmmm 格式
        lat_deg = int(abs(self.lat))
        lat_min = (abs(self.lat) - lat_deg) * 60.0
        lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
        lat_dir = "N" if self.lat >= 0 else "S"

        lon_deg = int(abs(self.lon))
        lon_min = (abs(self.lon) - lon_deg) * 60.0
        lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
        lon_dir = "E" if self.lon >= 0 else "W"

        # GGA 格式
        msg = (f"$GPGGA,123456.00,{lat_str},{lat_dir},{lon_str},{lon_dir},"
               f"4,12,0.9,{self.alt:.1f},M,0.0,M,,")

        # 计算校验和
        checksum = 0
        for ch in msg[1:]:
            checksum ^= ord(ch)
        return f"{msg}*{checksum:02X}\r\n"

    def generate_rmc(self) -> str:
        """生成 $GPRMC 语句（速度、航向）。"""
        lat_deg = int(abs(self.lat))
        lat_min = (abs(self.lat) - lat_deg) * 60.0
        lat_str = f"{lat_deg:02d}{lat_min:07.4f}"
        lat_dir = "N" if self.lat >= 0 else "S"

        lon_deg = int(abs(self.lon))
        lon_min = (abs(self.lon) - lon_deg) * 60.0
        lon_str = f"{lon_deg:03d}{lon_min:07.4f}"
        lon_dir = "E" if self.lon >= 0 else "W"

        speed_knots = self.speed / 0.514444
        msg = (f"$GPRMC,123456.00,A,{lat_str},{lat_dir},{lon_str},{lon_dir},"
               f"{speed_knots:.1f},{self.heading:.1f},280426,,,A")

        checksum = 0
        for ch in msg[1:]:
            checksum ^= ord(ch)
        return f"{msg}*{checksum:02X}\r\n"

    def send_frame(self) -> None:
        """发送一帧 GNSS 数据（GGA + RMC）。"""
        data = self.generate_gga() + self.generate_rmc()
        self.sock.sendto(data.encode("ascii"), (self.target_host, self.target_port))

    def update_position(self, dt: float) -> None:
        """根据速度和航向更新位置（简单线性运动）。"""
        if self.speed > 0:
            # 粗略计算（适用于小范围）
            dlat = self.speed * dt * math.cos(math.radians(self.heading)) / 111000.0
            dlon = self.speed * dt * math.sin(math.radians(self.heading)) / (111000.0 * math.cos(math.radians(self.lat)))
            self.lat += dlat
            self.lon += dlon


class ImuSimulator:
    """
    IMU 模拟器。
    生成二进制格式的 IMU 数据包（加速度 + 陀螺仪）。
    """

    def __init__(self, target_host: str, target_port: int):
        self.target_host = target_host
        self.target_port = target_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.time = 0.0

    def send_frame(self) -> None:
        """发送一帧 IMU 数据（静止状态：陀螺仪≈0，加速度≈重力）。"""
        # 二进制格式：8 个 float32（小端）
        data = struct.pack(
            "<8f",
            self.time,       # timestamp
            0.001,           # gyro_x (rad/s)
            -0.002,          # gyro_y
            0.0005,          # gyro_z
            0.1,             # accel_x (m/s²)
            0.05,            # accel_y
            9.81,            # accel_z (静止时≈重力)
            25.0,            # temperature (°C)
        )
        self.sock.sendto(data, (self.target_host, self.target_port))
        self.time += 0.005  # 每次递增 5ms


def main():
    parser = argparse.ArgumentParser(description="GNSS/IMU 数据模拟器")
    parser.add_argument(
        "--scenario",
        choices=["static", "moving"],
        default="static",
        help="场景：static=静止 / moving=运动",
    )
    parser.add_argument("--speed", type=float, default=1.5, help="运动速度（m/s）")
    parser.add_argument("--rate", type=int, default=10, help="GNSS 输出频率（Hz）")
    parser.add_argument("--imu-rate", type=int, default=200, help="IMU 输出频率（Hz）")
    parser.add_argument("--host", default="127.0.0.1", help="目标主机（主程序监听地址）")

    args = parser.parse_args()

    setup_logging(level="INFO")

    logger.info("=" * 60)
    logger.info("GNSS/IMU 数据模拟器")
    logger.info("场景: %s | GNSS 频率: %d Hz | IMU 频率: %d Hz",
                args.scenario, args.rate, args.imu_rate)
    logger.info("=" * 60)

    # 创建三台 GNSS 模拟器（对应 3 个接收机）
    gnss_sims = [
        GnssSimulator(args.host, 9001, "gantry_a1"),
        GnssSimulator(args.host, 9001, "gantry_a2"),
        GnssSimulator(args.host, 9001, "trolley"),
    ]

    # 运动场景设置速度
    if args.scenario == "moving":
        for sim in gnss_sims:
            sim.speed = args.speed

    # 创建 IMU 模拟器
    imu_sim = ImuSimulator(args.host, 9002)

    gnss_interval = 1.0 / args.rate
    imu_interval = 1.0 / args.imu_rate

    next_gnss_time = time.time()
    next_imu_time = time.time()

    logger.info("模拟器启动，按 Ctrl+C 停止")

    try:
        while True:
            now = time.time()

            # 发送 GNSS 数据
            if now >= next_gnss_time:
                for sim in gnss_sims:
                    sim.send_frame()
                    sim.update_position(gnss_interval)
                next_gnss_time += gnss_interval

            # 发送 IMU 数据
            if now >= next_imu_time:
                imu_sim.send_frame()
                next_imu_time += imu_interval

            time.sleep(0.001)  # 1ms 主循环
    except KeyboardInterrupt:
        logger.info("模拟器已停止")


if __name__ == "__main__":
    main()

