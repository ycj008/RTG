"""
数据模型：定位解算结果
包含大车、小车的完整输出，最终由 bridge_node 下发给 PLC。
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class DataSource(IntEnum):
    """结果数据来源"""
    GNSS_RTK_FIXED = 1   # GNSS RTK 固定解
    GNSS_RTK_FLOAT = 2   # GNSS RTK 浮点解
    IMU_COASTING = 3     # IMU 惯导补位（GNSS 丢星期间）
    INVALID = 0


@dataclass
class GantryResult:
    """
    大车定位解算结果。

    坐标基准：堆场局部坐标系（LYCS）
    偏移基准：以跑道中心线为零点，偏向堆场内为负，偏向堆场外为正。
    速度符号：大车值增大方向为正，减小为负。
    """
    timestamp: float = 0.0

    # ---- 双中心距离（距离堆场原点，米）----
    center_elec_side: float = 0.0    # 电气房侧中心距离堆场原点（米）
    center_engine_side: float = 0.0  # 柴油机侧中心距离堆场原点（米）

    # ---- 四个门腿相对跑道中心线偏移（米）----
    # 排列顺序：左前、左后、右前、右后
    leg_offsets: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])

    # ---- 速度（m/s）----
    speed: float = 0.0

    # ---- 姿态角（°）----
    heading: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0

    # ---- L-Point 坐标（堆场坐标系，米）----
    lpoint_x: float = 0.0
    lpoint_y: float = 0.0
    lpoint_z: float = 0.0

    data_source: DataSource = DataSource.INVALID


@dataclass
class TrolleyResult:
    """
    小车定位解算结果。

    坐标基准：RTG 局部坐标系（笛卡尔右手系）
    X 轴：沿轨道数值增大方向为正
    Z 轴：竖直向上为正
    速度符号：沿轨道增大方向为正。
    """
    timestamp: float = 0.0

    # ---- 小车两端天线相对 RTG 坐标系位置（米）----
    antenna1_x: float = 0.0
    antenna1_y: float = 0.0
    antenna1_z: float = 0.0

    antenna2_x: float = 0.0
    antenna2_y: float = 0.0
    antenna2_z: float = 0.0

    # ---- 小车中心位置（米）----
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0

    # ---- 距轨道起始点的实际行程（米）----
    travel_distance: float = 0.0

    # ---- 速度（m/s）----
    speed: float = 0.0

    data_source: DataSource = DataSource.INVALID


@dataclass
class PositionResult:
    """
    系统输出的完整定位结果，solver_node 组装后发布到 EventBus。
    bridge_node ��收并按协议下发给 PLC。
    """
    timestamp: float = 0.0
    yard_id: str = ""               # 当前所在堆场 ID

    gantry: GantryResult = field(default_factory=GantryResult)
    trolley: TrolleyResult = field(default_factory=TrolleyResult)

    # 系统健康状态
    gnss_fix_quality: int = 0       # 当前 GNSS 定位质量
    imu_coasting_active: bool = False
    imu_coasting_duration: float = 0.0   # 当前惯导补位已持续秒数

