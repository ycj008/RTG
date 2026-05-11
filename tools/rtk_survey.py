"""
运维工具：RTK 手持打点
用于工程实施第一阶段：在 RTK 固定解状态下采集堆场控制点。

使用方式：
    python tools/rtk_survey.py --yard yard_01 --type origin
    python tools/rtk_survey.py --yard yard_01 --type bay --bay-no 1
"""

import sys
import time
import argparse
import logging
from pathlib import Path

# 添加项目根目录到搜索路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logging
from src.utils.config_loader import init_config, get_config
from src.utils.database import GroundTruthDB
from src.driver.nmea_parser import parse_sentence
from src.models.gnss_data import GnssRaw, FixQuality
import socket

logger = logging.getLogger(__name__)


class RTKSurveyTool:
    """
    RTK 手持打点工具。
    连接手持 RTK 接收机（UDP），采集 N 帧取均值后存入数据库。
    """

    def __init__(
        self,
        db: GroundTruthDB,
        host: str = "0.0.0.0",
        port: int = 9999,
        frame_count: int = 10,
    ):
        self.db = db
        self.host = host
        self.port = port
        self.frame_count = frame_count

    def survey_point(
        self,
        yard_id: str,
        point_type: str,
        bay_no: int = None,
    ) -> bool:
        """
        采集单个控制点。

        :param yard_id:    堆场 ID
        :param point_type: 点类型 'origin' / 'bay' / 'magnet'
        :param bay_no:     贝位编号（type='bay' 时必填）
        :return:           是否成功
        """
        logger.info("开始采集 %s 堆场控制点: type=%s bay=%s",
                    yard_id, point_type, bay_no)
        logger.info("等待 RTK 固定解...")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        sock.bind((self.host, self.port))

        samples = []
        try:
            while len(samples) < self.frame_count:
                try:
                    data, _ = sock.recvfrom(4096)
                except socket.timeout:
                    continue

                text = data.decode("ascii", errors="ignore")
                for line in text.splitlines():
                    parsed = parse_sentence(line.strip())
                    if parsed and parsed.get("type") == "GGA":
                        # 检查 RTK 固定解
                        fix_q = parsed.get("fix_quality", 0)
                        if fix_q != int(FixQuality.RTK_FIXED):
                            print(f"\r等待 RTK 固定解... 当前: {FixQuality(fix_q).name}", end="")
                            continue

                        # 有效样本
                        samples.append({
                            "lat": parsed["lat"],
                            "lon": parsed["lon"],
                            "alt": parsed["alt"],
                        })
                        print(f"\r采集进度: {len(samples)}/{self.frame_count}", end="")

                        if len(samples) >= self.frame_count:
                            break
        finally:
            sock.close()

        if len(samples) < self.frame_count:
            logger.error("采集失败，样本数不足: %d/%d", len(samples), self.frame_count)
            return False

        # 计算均值
        lat_avg = sum(s["lat"] for s in samples) / len(samples)
        lon_avg = sum(s["lon"] for s in samples) / len(samples)
        alt_avg = sum(s["alt"] for s in samples) / len(samples)

        print()  # 换行
        logger.info("采集完成 | 均值: (%.8f, %.8f, %.3f)", lat_avg, lon_avg, alt_avg)

        # 存入数据库
        row_id = self.db.insert_survey_point(
            yard_id=yard_id,
            point_type=point_type,
            lat=lat_avg,
            lon=lon_avg,
            alt=alt_avg,
            bay_no=bay_no,
            frame_count=len(samples),
        )
        logger.info("已写入数据库，记录 ID: %d", row_id)
        return True


def main():
    parser = argparse.ArgumentParser(description="RTK 手持打点工具")
    parser.add_argument("--yard", required=True, help="堆场 ID，如 yard_01")
    parser.add_argument(
        "--type",
        required=True,
        choices=["origin", "bay", "magnet"],
        help="点类型：origin=堆场原点 / bay=贝位 / magnet=磁钉",
    )
    parser.add_argument("--bay-no", type=int, help="贝位编号（type=bay 时必填）")
    parser.add_argument("--host", default="0.0.0.0", help="监听主机（接收 RTK UDP）")
    parser.add_argument("--port", type=int, default=9999, help="监听端口")
    parser.add_argument("--frames", type=int, default=10, help="采样帧数（默认 10）")
    parser.add_argument("--db", default="data/ground_truth.db", help="数据库路径")

    args = parser.parse_args()

    # 校验参数
    if args.type == "bay" and args.bay_no is None:
        parser.error("--type=bay 时必须指定 --bay-no")

    # 初始化日志
    setup_logging(level="INFO")

    # 初始化数据库
    db = GroundTruthDB(args.db)

    # 创建工具实例
    tool = RTKSurveyTool(
        db=db,
        host=args.host,
        port=args.port,
        frame_count=args.frames,
    )

    # 执行采集
    logger.info("=" * 60)
    logger.info("RTK 手持打点工具")
    logger.info("=" * 60)
    success = tool.survey_point(
        yard_id=args.yard,
        point_type=args.type,
        bay_no=args.bay_no,
    )

    if success:
        logger.info("✓ 打点完成")
        return 0
    else:
        logger.error("✗ 打点失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

