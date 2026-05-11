"""
融合模块：扩展卡尔曼滤波（EKF）
实现松耦合 GNSS/IMU EKF，用于姿态平滑与位姿估计。

状态向量（15维）：
  x = [δpN, δpE, δpD,       # 位置误差（NED，m）
       δvN, δvE, δvD,       # 速度误差（NED，m/s）
       δφ,  δθ,  δψ,        # 姿态误差（rad）
       bgx, bgy, bgz,       # 陀螺仪偏置（rad/s）
       bax, bay, baz]       # 加速度计偏置（m/s²）

误差状态 EKF（Error-State Kalman Filter，ESKF）：
  - 在 ImuMechanization 标称值附近线性化
  - 每次 GNSS 更新后将误差状态回代到标称状态
"""

import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 状态维数
N_STATE = 15
# 观测维数（GNSS 位置 NED 3 维）
N_OBS = 3


class EKF:
    """
    误差状态卡尔曼滤波器（ESKF）。

    使用方式：
        ekf = EKF(sigma_pos=0.05, sigma_vel=0.01, ...)
        ekf.predict(F, Q)            # IMU 积分后调用（更新协方差）
        ekf.update(z, H, R)          # GNSS 到来时调用（位置量测）
        correction = ekf.state       # 读取误差状态修正量
        ekf.reset_state()            # 误差回代后清零
    """

    def __init__(
        self,
        sigma_pos: float = 0.05,
        sigma_vel: float = 0.01,
        sigma_att: float = 0.001,
        sigma_gyro_bias: float = 1e-5,
        sigma_accel_bias: float = 1e-4,
        sigma_gnss_h: float = 0.03,
        sigma_gnss_v: float = 0.05,
    ):
        """
        :param sigma_pos/vel/att:         过程噪声初始标准差
        :param sigma_gyro/accel_bias:     传感器偏置过程噪声
        :param sigma_gnss_h/v:            GNSS 水平/垂直量测噪声（m）
        """
        # 误差状态（均值为 0）
        self._x = np.zeros(N_STATE)

        # 协方差矩阵 P（初始化为过程噪声量级）
        p0 = np.concatenate([
            [sigma_pos ** 2]   * 3,
            [sigma_vel ** 2]   * 3,
            [sigma_att ** 2]   * 3,
            [sigma_gyro_bias ** 2]  * 3,
            [sigma_accel_bias ** 2] * 3,
        ])
        self._P = np.diag(p0)

        # 过程噪声谱密度（连续时间）
        self._q_pos          = sigma_pos ** 2
        self._q_vel          = sigma_vel ** 2
        self._q_att          = sigma_att ** 2
        self._q_gyro_bias    = sigma_gyro_bias ** 2
        self._q_accel_bias   = sigma_accel_bias ** 2

        # 量测噪声协方差 R（3×3，NED 位置）
        self._R_gnss = np.diag([
            sigma_gnss_h ** 2,
            sigma_gnss_h ** 2,
            sigma_gnss_v ** 2,
        ])

    @property
    def state(self) -> np.ndarray:
        """当前误差状态向量（15维）。"""
        return self._x.copy()

    @property
    def covariance(self) -> np.ndarray:
        """当前协方差矩阵（15×15）。"""
        return self._P.copy()

    def build_F(
        self,
        accel_nav: np.ndarray,
        R_bn: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        """
        构建离散化状态转移矩阵 F（15×15）。

        :param accel_nav: 导航系比力向量 [aN, aE, aD]（m/s²）
        :param R_bn:      机体到导航坐标系的旋转矩阵（3×3）
        :param dt:        积分步长（秒）
        :return:          离散 F 矩阵
        """
        F = np.eye(N_STATE)

        # δp += δv * dt
        F[0:3, 3:6] = np.eye(3) * dt

        # δv += (-[f×] * δψ + R_bn * δba) * dt
        # [f×] 是比力的反对称矩阵
        ax, ay, az = accel_nav
        skew_a = np.array([
            [ 0,  -az,  ay],
            [ az,   0, -ax],
            [-ay,  ax,   0],
        ])
        F[3:6, 6:9]  = -skew_a * dt          # 姿态误差对速度影响
        F[3:6, 12:15] = R_bn * dt             # 加速度计偏置对速度影响

        # δψ += R_bn * δbg * dt（陀螺偏置对姿态影响）
        F[6:9, 9:12] = -R_bn * dt

        # 偏置随机游走（一阶马尔可夫，此处简化为常数）
        # F[9:15, 9:15] 保持单位矩阵

        return F

    def build_Q(self, dt: float) -> np.ndarray:
        """
        构建过程噪声协方差矩阵 Q（15×15）。

        :param dt: 积分步长（秒）
        """
        q_diag = np.concatenate([
            [self._q_pos]          * 3,
            [self._q_vel]          * 3,
            [self._q_att]          * 3,
            [self._q_gyro_bias]    * 3,
            [self._q_accel_bias]   * 3,
        ]) * dt
        return np.diag(q_diag)

    def predict(self, F: np.ndarray, Q: np.ndarray) -> None:
        """
        EKF 预测步：更新协方差，误差状态保持为零（误差状态在更新后清零）。

        :param F: 离散状态转移矩阵（15×15）
        :param Q: 过程噪声协方差矩阵（15×15）
        """
        self._x = F @ self._x
        self._P = F @ self._P @ F.T + Q

    def update_gnss_position(
        self,
        gnss_pos_ned: np.ndarray,
        nominal_pos_ned: np.ndarray,
    ) -> np.ndarray:
        """
        GNSS 位置量测更新（NED 坐标系）。

        :param gnss_pos_ned:    GNSS 量测位置 [N, E, D]（m）
        :param nominal_pos_ned: IMU 推算的标称位置 [N, E, D]（m）
        :return:                误差状态修正量（15维），供回代到标称状态
        """
        # 量测矩阵 H（3×15）：只观测位置误差 δp（前3分量）
        H = np.zeros((N_OBS, N_STATE))
        H[0:3, 0:3] = np.eye(3)

        # 量测残差 z = gnss - nominal
        z = gnss_pos_ned - nominal_pos_ned

        # 卡尔曼增益
        S = H @ self._P @ H.T + self._R_gnss
        K = self._P @ H.T @ np.linalg.inv(S)

        # 状态更新
        self._x = self._x + K @ z

        # 协方差更新（Joseph 形式，保持正定性）
        I_KH = np.eye(N_STATE) - K @ H
        self._P = I_KH @ self._P @ I_KH.T + K @ self._R_gnss @ K.T

        logger.debug(
            "EKF GNSS 更新 | 残差=[%.4f, %.4f, %.4f] m | 位置修正=[%.4f, %.4f, %.4f] m",
            z[0], z[1], z[2],
            self._x[0], self._x[1], self._x[2],
        )
        return self._x.copy()

    def reset_state(self) -> None:
        """
        误差状态回代到标称状态后，将误差状态清零。
        （由 fusion_node 在每次更新后调用）
        """
        self._x[:] = 0.0

    def get_pos_correction(self) -> np.ndarray:
        """返回位置误差修正量 [δpN, δpE, δpD]（m）。"""
        return self._x[0:3].copy()

    def get_vel_correction(self) -> np.ndarray:
        """返回速度误差修正量 [δvN, δvE, δvD]（m/s）。"""
        return self._x[3:6].copy()

    def get_att_correction_deg(self) -> np.ndarray:
        """返回姿态误差修正量 [δroll, δpitch, δheading]（°）。"""
        return np.degrees(self._x[6:9])

    def get_gyro_bias(self) -> np.ndarray:
        """返回陀螺仪偏置估计值 [bgx, bgy, bgz]（rad/s）。"""
        return self._x[9:12].copy()

    def get_accel_bias(self) -> np.ndarray:
        """返回加速度计偏置估计值 [bax, bay, baz]（m/s²）。"""
        return self._x[12:15].copy()

