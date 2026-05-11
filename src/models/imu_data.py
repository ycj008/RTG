"""
数据模型：IMU 原始数据
"""

from dataclasses import dataclass


@dataclass
class ImuRaw:
    """
    IMU（惯性测量单元）单帧数据。

    来源：driver_node 解析 IMU UDP 数据包���填充，
    发布到 EventBus.TOPIC_IMU_RAW 主题。
    """
    # 时间戳（UNIX 时间，秒）
    timestamp: float = 0.0

    # ---- 三轴角速度（rad/s，IMU 机体坐标系）----
    gyro_x: float = 0.0   # 绕 X 轴（前后行驶轴，Roll 轴）
    gyro_y: float = 0.0   # 绕 Y 轴（横向，Pitch 轴）
    gyro_z: float = 0.0   # 绕 Z 轴（垂直，Yaw 轴）

    # ---- 三轴线加速度（m/s²，IMU 机体坐标系，含重力）----
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0

    # ---- 温度（°C，用于温漂补偿，可选）----
    temperature: float = 25.0

