"""
驱动模块：GNSS 接收机 UDP 监听
每台接收机对应一个 GnssReceiver 实例，运行在独立线程中。
收到 UDP 数据包后解析 NMEA 语句，组装 GnssRaw 并通过 EventBus 发布。
"""

import socket
import threading
import logging
import time
from typing import Optional

from src.core.event_bus import get_bus, EventBus
from src.models.gnss_data import GnssRaw, FixQuality
from src.driver.nmea_parser import parse_sentence
from src.solver.coordinate_transform import wgs84_to_ecef

logger = logging.getLogger(__name__)

# UDP 接收缓冲区大小
_UDP_BUFFER_SIZE = 4096
# 接收机数据超时告警阈值（秒）
_DATA_TIMEOUT_S = 2.0


class GnssReceiver(threading.Thread):
    """
    单台 GNSS 接收机的 UDP 数据接收与解析线程。

    每个 UDP 数据包可能包含多条 NMEA 语句（以 \\r\\n 分隔）。
    解析完成后合并为一帧 GnssRaw，发布到 EventBus。
    """

    def __init__(
        self,
        receiver_id: str,
        host: str,
        port: int,
        bus: Optional[EventBus] = None,
    ):
        """
        :param receiver_id: 接收机标识，如 "gantry_a1"
        :param host:        绑定的本机 IP（接收机向此地址推送 UDP）
        :param port:        监听端口
        :param bus:         事件总线（默认使用全局单例）
        """
        super().__init__(name=f"GnssReceiver-{receiver_id}", daemon=True)
        self.receiver_id = receiver_id
        self.host = host
        self.port = port
        self._bus = bus or get_bus()
        self._stop_event = threading.Event()

        # 当前帧缓存（在一个包的多条语句间累积状态）
        self._frame: GnssRaw = GnssRaw(receiver_id=receiver_id)
        self._last_data_time: float = 0.0

    def stop(self) -> None:
        """通知接收线程停止。"""
        self._stop_event.set()

    def run(self) -> None:
        """线程主循环：持续监听 UDP 并解析数据。"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)    # 允许周期检查 stop_event

        try:
            sock.bind((self.host, self.port))
            logger.info("[%s] UDP 监听启动: %s:%d",
                        self.receiver_id, self.host, self.port)

            while not self._stop_event.is_set():
                try:
                    data, addr = sock.recvfrom(_UDP_BUFFER_SIZE)
                except socket.timeout:
                    # 超时检查数据是否中断
                    if (self._last_data_time > 0
                            and time.time() - self._last_data_time > _DATA_TIMEOUT_S):
                        logger.warning("[%s] 超过 %.1f s 未收到数据",
                                       self.receiver_id, _DATA_TIMEOUT_S)
                    continue
                except OSError as e:
                    logger.error("[%s] Socket 错误: %s", self.receiver_id, e)
                    break

                self._last_data_time = time.time()
                self._process_packet(data)

        finally:
            sock.close()
            logger.info("[%s] UDP 监听已关闭", self.receiver_id)

    # ------------------------------------------------------------------
    # 内部：数据包处理
    # ------------------------------------------------------------------
    def _process_packet(self, data: bytes) -> None:
        """
        处理一个 UDP 数据包。
        一个包内可能有多条 NMEA 语句，全部解析后合并成一帧发布。
        """
        try:
            text = data.decode("ascii", errors="ignore")
        except UnicodeDecodeError:
            return

        sentences = [s.strip() for s in text.splitlines() if s.strip()]
        frame_updated = False

        for sentence in sentences:
            result = parse_sentence(sentence)
            if result is None:
                continue

            self._merge_into_frame(result)
            frame_updated = True

        # 包内所有语句解析完后，若包含位置信息则发布本帧
        if frame_updated and self._frame.is_valid:
            self._publish_frame()

    def _merge_into_frame(self, parsed: dict) -> None:
        """
        将单条 NMEA 解析结果合并到当前帧缓存中。
        不同类型的语句填充 GnssRaw 的不同字段。
        """
        msg_type = parsed.get("type")

        if msg_type == "GGA":
            self._frame.timestamp = parsed["timestamp"]
            self._frame.latitude = parsed["lat"]
            self._frame.longitude = parsed["lon"]
            self._frame.altitude = parsed["alt"]
            self._frame.fix_quality = FixQuality(parsed["fix_quality"])
            self._frame.num_satellites = parsed["num_sats"]
            self._frame.hdop = parsed["hdop"]

        elif msg_type == "RMC":
            self._frame.speed_mps = parsed["speed_mps"]
            self._frame.course_deg = parsed["course_deg"]

        elif msg_type == "HDT":
            self._frame.heading = parsed["heading_deg"]

        elif msg_type == "ATTITUDE":
            self._frame.heading = parsed["heading_deg"]
            self._frame.pitch = parsed.get("pitch_deg")
            self._frame.roll = parsed.get("roll_deg")

    def _publish_frame(self) -> None:
        """
        将当前帧转换为 ECEF 坐标并发布到 EventBus。
        发布后重置帧缓存（保留 receiver_id）。
        """
        # 附加 ECEF 坐标（供 EKF 直接使用）
        ex, ey, ez = wgs84_to_ecef(
            self._frame.latitude,
            self._frame.longitude,
            self._frame.altitude,
        )
        self._frame.ecef_x = ex
        self._frame.ecef_y = ey
        self._frame.ecef_z = ez

        self._bus.publish(EventBus.TOPIC_GNSS_RAW, self._frame)

        # 重置帧缓存
        self._frame = GnssRaw(receiver_id=self.receiver_id)

