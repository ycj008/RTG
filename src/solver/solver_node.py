"""
解算节点：solver_node
订阅 fusion_node 输出的融合状态，执行完整解算流程：
  1. 自动识别当前堆场
  2. 坐标系变换（WGS84 → LYCS）
  3. L-Point 刚体变换（大车 + 小车）
  4. B 车矩阵修正（如已完成校准）
  5. 输出 PositionResult 到 EventBus
"""

import logging
import time
import numpy as np
from typing import Optional

from src.core.event_bus import get_bus, EventBus
from src.models.positioning import (
    PositionResult, GantryResult, TrolleyResult, DataSource
)
from src.solver.lpoint_solver import LPointSolver
from src.solver.yard_manager import YardManager
from src.solver.calibration import BVehicleCalibrator
from src.utils.config_loader import get_config
from src.utils.database import GroundTruthDB

logger = logging.getLogger(__name__)


class SolverNode:
    """
    解算节点：将融合状态转换为可下发给 PLC 的最终定位结果。

    数据流：
      fusion_node → TOPIC_FUSED_STATE → SolverNode → TOPIC_POSITION_RESULT
    """

    def __init__(
        self,
        yard_manager: YardManager,
        db: GroundTruthDB,
        bus: Optional[EventBus] = None,
    ):
        cfg = get_config()
        self._bus = bus or get_bus()
        self._yard_manager = yard_manager
        self._db = db

        # 大车两台接收机的 L-Point 解算器
        vp = cfg.get("gantry", {})
        self._solver_a1 = LPointSolver(
            cfg.get("gantry.antenna_a1.L_arm", [0, 0, -8.45])
        )
        self._solver_a2 = LPointSolver(
            cfg.get("gantry.antenna_a2.L_arm", [0, 0, -8.45])
        )
        self._w_span = cfg.get("gantry.W_span", 20.0)

        # 小车解算器（两根天线）
        self._solver_c1 = LPointSolver(
            cfg.get("trolley.antenna_c1.L_arm", [0, 0.5, -3.1])
        )
        self._solver_c2 = LPointSolver(
            cfg.get("trolley.antenna_c2.L_arm", [0, -0.5, -3.1])
        )

        # B 车校准器（每个堆场独立）
        self._calibrators: dict[str, BVehicleCalibrator] = {}

        # 小车行程零点（初始化后记录）
        self._trolley_origin_x: Optional[float] = None
        self._last_trolley_x: Optional[float] = None
        self._trolley_speed: float = 0.0
        self._last_trolley_time: float = 0.0

        # 大车速度
        self._last_gantry_x: Optional[float] = None
        self._gantry_speed: float = 0.0
        self._last_gantry_time: float = 0.0

        # 订阅融合状态
        self._bus.subscribe(EventBus.TOPIC_FUSED_STATE, self._on_fused_state)
        logger.info("SolverNode 初始化完成")

    # ------------------------------------------------------------------
    # 回调：处理融合状态
    # ------------------------------------------------------------------
    def _on_fused_state(self, state: dict) -> None:
        """
        接收来自 fusion_node 的融合状态字典。

        期望字段：
          gantry_a1: {ecef_x, ecef_y, ecef_z, roll, pitch, heading, timestamp}
          gantry_a2: {ecef_x, ecef_y, ecef_z, roll, pitch, heading}
          trolley:   {ecef_x, ecef_y, ecef_z, roll, pitch, heading, timestamp}
          source:    DataSource 枚举值
        """
        try:
            result = self._solve(state)
            if result:
                self._bus.publish(EventBus.TOPIC_POSITION_RESULT, result)
        except Exception as exc:
            logger.exception("解算异常: %s", exc)

    # ------------------------------------------------------------------
    # 核心解算
    # ------------------------------------------------------------------
    def _solve(self, state: dict) -> Optional[PositionResult]:
        """
        完整解算流程，返回 PositionResult。
        """
        now = time.time()
        ga1 = state.get("gantry_a1", {})
        ga2 = state.get("gantry_a2", {})
        tly = state.get("trolley", {})
        source = state.get("source", DataSource.INVALID)

        if not ga1 or not tly:
            return None

        # ---- 1. 识别当前堆场 ----
        yard_id = self._yard_manager.detect_yard(
            lat=ga1.get("lat", 0.0),
            lon=ga1.get("lon", 0.0),
        )
        transform = self._yard_manager.get_transform(yard_id)
        if transform is None:
            logger.warning("无法识别当前堆场，跳过本帧解算")
            return None

        # ---- 2. 大车解算 ----
        gantry_result = self._solve_gantry(ga1, ga2, transform, yard_id, now)

        # ---- 3. 小车解算 ----
        trolley_result = self._solve_trolley(tly, transform, now)

        # ---- 4. 组装结果 ----
        result = PositionResult(
            timestamp=now,
            yard_id=yard_id or "",
            gantry=gantry_result,
            trolley=trolley_result,
            gnss_fix_quality=int(state.get("fix_quality", 0)),
            imu_coasting_active=state.get("imu_coasting", False),
            imu_coasting_duration=state.get("imu_coasting_duration", 0.0),
        )
        return result

    def _solve_gantry(self, ga1: dict, ga2: dict, transform, yard_id: str,
                      now: float) -> GantryResult:
        """
        大车定位解算：
          - A1 天线 L-Point → LYCS X 轴（电气房侧中心）
          - A2 天线 L-Point → LYCS X 轴（柴油机侧中心）
          - 四门腿偏移 = L-Point Y 坐标（相对跑道中心线）
        """
        gantry = GantryResult(timestamp=now)

        # A1 L-Point
        gps_a1 = np.array([ga1["ecef_x"], ga1["ecef_y"], ga1["ecef_z"]])
        roll_a1 = ga1.get("roll", 0.0)
        pitch_a1 = ga1.get("pitch", 0.0)
        hdg_a1 = ga1.get("heading", 0.0)

        # 查询当前贝位 Z 补丁（简化：用大车 X 坐标估算贝位）
        lp_a1_ecef = self._solver_a1.solve(gps_a1, roll_a1, pitch_a1, hdg_a1)
        lx_a1, ly_a1, lz_a1 = transform.ecef_to_lycs(*lp_a1_ecef)

        # A2 L-Point（若有）
        if ga2:
            gps_a2 = np.array([ga2["ecef_x"], ga2["ecef_y"], ga2["ecef_z"]])
            lp_a2_ecef = self._solver_a2.solve(
                gps_a2, ga2.get("roll", 0.0), ga2.get("pitch", 0.0), ga2.get("heading", 0.0)
            )
            lx_a2, ly_a2, lz_a2 = transform.ecef_to_lycs(*lp_a2_ecef)
        else:
            lx_a2, ly_a2 = lx_a1, ly_a1

        # 双中心距离（沿 X 轴，即大车行驶方向）
        gantry.center_elec_side = lx_a1
        gantry.center_engine_side = lx_a2
        gantry.lpoint_x = (lx_a1 + lx_a2) / 2.0
        gantry.lpoint_y = (ly_a1 + ly_a2) / 2.0
        gantry.lpoint_z = (lz_a1 + (lz_a1 if not ga2 else lz_a2)) / 2.0

        # 四门腿相对跑道中心线偏移（Y 方向）
        # 简化：左侧两腿 = ly_a1，右侧两腿 = ly_a1 + W_span
        half_span = self._w_span / 2.0
        gantry.leg_offsets = [
            ly_a1,                      # 左前腿
            ly_a1,                      # 左后腿
            ly_a1 + self._w_span,       # 右前腿
            ly_a1 + self._w_span,       # 右后腿
        ]

        # B 车变换矩阵修正
        M = self._yard_manager.get_b_matrix(yard_id) if yard_id else None
        if M is not None:
            cx, cy = _apply_matrix(M, gantry.lpoint_x, gantry.lpoint_y)
            # 同步修正双中心
            shift = cx - gantry.lpoint_x
            gantry.lpoint_x = cx
            gantry.lpoint_y = cy
            gantry.center_elec_side += shift
            gantry.center_engine_side += shift

        # 大车速度
        if self._last_gantry_x is not None and self._last_gantry_time > 0:
            dt = now - self._last_gantry_time
            if dt > 0:
                self._gantry_speed = (gantry.lpoint_x - self._last_gantry_x) / dt
        self._last_gantry_x = gantry.lpoint_x
        self._last_gantry_time = now
        gantry.speed = self._gantry_speed
        gantry.heading = ga1.get("heading", 0.0)
        gantry.pitch = ga1.get("pitch", 0.0)
        gantry.roll = ga1.get("roll", 0.0)
        gantry.data_source = source
        return gantry

    def _solve_trolley(self, tly: dict, transform, now: float) -> TrolleyResult:
        """
        小车定位解算：输出两端天线在 RTG 坐标系下的坐标及行程。
        """
        trolley = TrolleyResult(timestamp=now)

        gps_c = np.array([tly["ecef_x"], tly["ecef_y"], tly["ecef_z"]])
        roll_c = tly.get("roll", 0.0)
        pitch_c = tly.get("pitch", 0.0)
        hdg_c = tly.get("heading", 0.0)

        lp_c1 = self._solver_c1.solve(gps_c, roll_c, pitch_c, hdg_c)
        lp_c2 = self._solver_c2.solve(gps_c, roll_c, pitch_c, hdg_c)

        x1, y1, z1 = transform.ecef_to_lycs(*lp_c1)
        x2, y2, z2 = transform.ecef_to_lycs(*lp_c2)

        trolley.antenna1_x, trolley.antenna1_y, trolley.antenna1_z = x1, y1, z1
        trolley.antenna2_x, trolley.antenna2_y, trolley.antenna2_z = x2, y2, z2
        trolley.center_x = (x1 + x2) / 2.0
        trolley.center_y = (y1 + y2) / 2.0
        trolley.center_z = (z1 + z2) / 2.0

        # 行程（相对初始零点）
        if self._trolley_origin_x is None:
            self._trolley_origin_x = trolley.center_x
        trolley.travel_distance = trolley.center_x - self._trolley_origin_x

        # 小车速度
        if self._last_trolley_x is not None and self._last_trolley_time > 0:
            dt = now - self._last_trolley_time
            if dt > 0:
                self._trolley_speed = (trolley.center_x - self._last_trolley_x) / dt
        self._last_trolley_x = trolley.center_x
        self._last_trolley_time = now
        trolley.speed = self._trolley_speed
        trolley.data_source = tly.get("source", DataSource.INVALID)
        return trolley

    # ------------------------------------------------------------------
    # 校准接口（供 bridge_node 或工具调用）
    # ------------------------------------------------------------------
    def add_calibration_point(
        self,
        yard_id: str,
        measured_xy: tuple,
        reference_xy: tuple,
    ) -> None:
        """
        添加 B 车校准点对。满 3 点后自动执行校准。

        :param yard_id:       堆场 ID
        :param measured_xy:   RTG 实测 (x, y)（米）
        :param reference_xy:  参考真值 (x, y)（米）
        """
        if yard_id not in self._calibrators:
            self._calibrators[yard_id] = BVehicleCalibrator()

        calibrator = self._calibrators[yard_id]
        count = calibrator.add_point(measured_xy, reference_xy)

        if calibrator.is_ready:
            M = calibrator.compute_transform()
            self._yard_manager.save_b_matrix(yard_id, M)
            logger.info("B 车校准完成，矩阵已保存（堆场 %s）", yard_id)

    def reset_trolley_origin(self) -> None:
        """重置小车行程零点。"""
        self._trolley_origin_x = None
        logger.info("小车行程零点已重置")


def _apply_matrix(M: np.ndarray, x: float, y: float):
    """用 3×3 齐次矩阵变换 2D 点。"""
    p = M @ np.array([x, y, 1.0])
    return float(p[0]), float(p[1])

