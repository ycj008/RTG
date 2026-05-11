"""
融合模块：IMU 机械编排（惯性导航推算）
在 GNSS 丢星期间，利用 IMU 加速度计和陀螺仪进行位姿积分推算（Dead Reckoning）。

坐标系：局部导航坐标系（North-East-Down，NED）
积分方式：欧拉前向积分（适合 ≤10s 短时补位需求）
"""

import math
import numpy as np
import logging
from dataclasses import dataclass, field

from src.solver.attitude import euler_to_rotation_matrix

logger = logging.getLogger(__name__)

# 重力加速度（m/s²）
GRAVITY = 9.80665


@dataclass
class ImuState:
    """IMU 惯性推算的当前状态（NED 坐标系）。"""
    # 位置（m），相对于推算起始点
    pos_n: float = 0.0
    pos_e: float = 0.0
    pos_d: float = 0.0

    # 速度（m/s）
    vel_n: float = 0.0
    vel_e: float = 0.0
    vel_d: float = 0.0

    # 姿态（°）
    roll: float = 0.0
    pitch: float = 0.0
    heading: float = 0.0

    # 陀螺仪偏置（rad/s），由 EKF 估计后注入
    gyro_bias: np.ndarray = field(default_factory=lambda: np.zeros(3))

    # 加速度计偏置（m/s²），由 EKF 估计后注入
    accel_bias: np.ndarray = field(default_factory=lambda: np.zeros(3))

    # 积分累计时长（秒）
    coasting_duration: float = 0.0


class ImuMechanization:
    """
    IMU 机械编排器：执行 IMU → 位姿积分。

    使用方式：
        mech = ImuMechanization()
        mech.initialize(state)           # 从 GNSS 最后已知状态初始化
        mech.propagate(gyro, accel, dt)  # 每次收到 IMU 数据时调用
        state = mech.state               # 读取当前推算状态
    """

    def __init__(self):
        self._state = ImuState()
        self._initialized = False

    @property
    def state(self) -> ImuState:
        """当前推算状态。"""
        return self._state

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def initialize(
        self,
        pos_ned: tuple,
        vel_ned: tuple,
        roll_deg: float,
        pitch_deg: float,
        heading_deg: float,
        gyro_bias: np.ndarray = None,
        accel_bias: np.ndarray = None,
    ) -> None:
        """
        用 GNSS 当前状态初始化推算起始点。

        :param pos_ned:    NED 位置 (N, E, D)，单位米，相对于某参考点
        :param vel_ned:    NED 速度 (vN, vE, vD)，单位 m/s
        :param roll_deg:   横滚角（°）
        :param pitch_deg:  俯仰角（°）
        :param heading_deg:航向角（°）
        """
        s = self._state
        s.pos_n, s.pos_e, s.pos_d = pos_ned
        s.vel_n, s.vel_e, s.vel_d = vel_ned
        s.roll = roll_deg
        s.pitch = pitch_deg
        s.heading = heading_deg
        s.coasting_duration = 0.0
        if gyro_bias is not None:
            s.gyro_bias = gyro_bias.copy()
        if accel_bias is not None:
            s.accel_bias = accel_bias.copy()
        self._initialized = True
        logger.debug("IMU 推算初始化完成: pos=(%.3f, %.3f, %.3f) att=(%.2f, %.2f, %.2f)",
                     *pos_ned, roll_deg, pitch_deg, heading_deg)

    def propagate(
        self,
        gyro_raw: np.ndarray,
        accel_raw: np.ndarray,
        dt: float,
    ) -> None:
        """
        单步 IMU 积分（欧拉前向法）。

        :param gyro_raw:  陀螺仪原始值 [gx, gy, gz]（rad/s，机体系）
        :param accel_raw: 加速度计原始值 [ax, ay, az]（m/s²，机体系，含重力）
        :param dt:        积分步长（秒）
        """
        if not self._initialized:
            logger.warning("IMU 推算未初始化，跳过")
            return

        s = self._state

        # 1. 去除偏置
        gyro = gyro_raw - s.gyro_bias
        accel = accel_raw - s.accel_bias

        # 2. 更新姿态（机体角速度 → 欧拉角导数）
        phi   = math.radians(s.roll)
        theta = math.radians(s.pitch)

        # 欧拉角运动学方程（小角近似时有效）
        # [roll_dot, pitch_dot, heading_dot]^T = T * gyro_body
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        cos_theta = math.cos(theta)
        # 防止俯仰角奇异（±90°）
        if abs(cos_theta) < 1e-6:
            cos_theta = 1e-6

        roll_dot    = gyro[0] + sin_phi * math.tan(theta) * gyro[1] + cos_phi * math.tan(theta) * gyro[2]
        pitch_dot   = cos_phi * gyro[1] - sin_phi * gyro[2]
        heading_dot = (sin_phi * gyro[1] + cos_phi * gyro[2]) / cos_theta

        s.roll    += math.degrees(roll_dot)    * dt
        s.pitch   += math.degrees(pitch_dot)   * dt
        s.heading += math.degrees(heading_dot) * dt
        s.heading  = s.heading % 360.0         # 归一化到 [0, 360)

        # 3. 旋转矩阵（机体 → 导航）
        R = euler_to_rotation_matrix(s.roll, s.pitch, s.heading)

        # 4. 比力（比力 = 加速度计减去重力在导航系的分量）
        g_ned = np.array([0.0, 0.0, GRAVITY])     # NED 中重力朝下（D+）
        specific_force_body = accel
        a_nav = R @ specific_force_body - g_ned   # 导航系加速度

        # 5. 更新速度（m/s）
        s.vel_n += a_nav[0] * dt
        s.vel_e += a_nav[1] * dt
        s.vel_d += a_nav[2] * dt

        # 6. 更新位置（m）
        s.pos_n += s.vel_n * dt
        s.pos_e += s.vel_e * dt
        s.pos_d += s.vel_d * dt

        # 7. 累计时长
        s.coasting_duration += dt

    def reset(self) -> None:
        """清除初始化状态（GNSS 恢复后调用）。"""
        self._initialized = False
        self._state = ImuState()

