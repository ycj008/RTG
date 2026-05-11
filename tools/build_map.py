"""
运维工具：A 车跑车建图（动态残差修正）
用于工程实施第二阶段：A 车在贝位停靠，对比 RTK 真值与实时解算值，
记录 Z 轴垂直偏差补丁到数据库。

使用方式：
    python tools/build_map.py --yard yard_01 --bay 1
    # A 车停靠在 1 号贝位，等待定位稳定后按回车记录偏差
"""

import sys
import time
import argparse
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logging
from src.utils.config_loader import init_config
from src.utils.database import GroundTruthDB
from src.core.event_bus import get_bus, EventBus
from src.models.positioning import PositionResult

logger = logging.getLogger(__name__)


class BuildMapTool:
    """
    A 车建图工具。
    订阅定位结果，对比数据库中的 RTK 真值，计算 Z 轴残差并存入数据库。
    """

    def __init__(self, db: GroundTruthDB, yard_id: str):
        self.db = db
        self.yard_id = yard_id
        self._latest_result: PositionResult = None
        self._bus = get_bus()
        self._bus.subscribe(EventBus.TOPIC_POSITION_RESULT, self._on_result)

    def _on_result(self, result: PositionResult) -> None:
        """接收实时定位结果。"""
        if result.yard_id == self.yard_id:
            self._latest_result = result

    def calibrate_bay(self, bay_no: int) -> bool:
        """
        A 车停靠在指定贝位，采集 Z 轴残差。

        :param bay_no: 贝位编号
        :return:       是否成功
        """
        logger.info("开始标定贝位 %d（堆场 %s）", bay_no, self.yard_id)

        # 查询 RTK 打点真值
        points = self.db.get_survey_points(self.yard_id, point_type="bay")
        ref_point = None
        for p in points:
            if p["bay_no"] == bay_no:
                ref_point = p
                break

        if ref_point is None:
            logger.error("数据库中找不到贝位 %d 的 RTK 打点记录", bay_no)
            return False

        # 从 local_z（如果已计算）或从 WGS84 反推得到参考 Z
        if ref_point.get("local_z") is not None:
            ref_z = ref_point["local_z"]
        else:
            # 简化：假设参考点的 Z 为椭球高（实际需通过坐标变换）
            ref_z = ref_point["alt"]
            logger.warning("RTK 打点无局部坐标，使用椭球高作为参考")

        logger.info("参考 Z 坐标（RTK 真值）: %.4f m", ref_z)
        logger.info("等待 A 车定位稳定...")

        # 等待用户确认 A 车已停稳
        input("请确保 A 车已停靠在贝位 %d，按回车继续..." % bay_no)

        # 采集多帧取均值
        samples = []
        logger.info("开始采集定位数据（共 20 帧）...")
        for i in range(20):
            time.sleep(0.1)
            if self._latest_result:
                samples.append(self._latest_result.gantry.lpoint_z)
                print(f"\r采集进度: {len(samples)}/20", end="")

        if len(samples) < 10:
            logger.error("采集样本不足: %d", len(samples))
            return False

        print()  # 换行
        measured_z = sum(samples) / len(samples)
        logger.info("实时解算 Z 坐标（均值）: %.4f m", measured_z)

        # 计算残差
        delta_z = measured_z - ref_z
        logger.info("Z 轴偏差: %.4f m（正=实测偏高）", delta_z)

        # 写入数据库
        self.db.upsert_z_patch(self.yard_id, bay_no, delta_z)
        logger.info("✓ 残差补丁已保存")
        return True


def main():
    parser = argparse.ArgumentParser(description="A 车跑车建图工具")
    parser.add_argument("--yard", required=True, help="堆场 ID")
    parser.add_argument("--bay", type=int, required=True, help="贝位编号")
    parser.add_argument("--db", default="data/ground_truth.db", help="数据库路径")

    args = parser.parse_args()

    setup_logging(level="INFO")
    init_config("config/system.yaml", "config/yard_config.yaml")

    db = GroundTruthDB(args.db)
    tool = BuildMapTool(db, args.yard)

    logger.info("=" * 60)
    logger.info("A 车建图工具 - Z 轴残差标定")
    logger.info("=" * 60)

    # 注意：本工具需在主程序运行时使用（EventBus 已有数据发布）
    logger.warning("！请确保主程序 src/main.py 正在运行")

    success = tool.calibrate_bay(args.bay)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

