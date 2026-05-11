"""
工具：系统诊断
检查 RTG 系统的配置、网络连通性、数据完整性等。

使用方式：
    python tools/diagnostic.py
"""

import sys
import socket
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logging
from src.utils.config_loader import Config
from src.utils.database import GroundTruthDB
import logging

logger = logging.getLogger(__name__)


def check_config_files() -> bool:
    """检查配置文件是否存在。"""
    logger.info("1. 检查配置文件...")
    files = [
        "config/system.yaml",
        "config/vehicle_params.yaml",
        "config/yard_config.yaml",
    ]
    all_ok = True
    for f in files:
        if os.path.exists(f):
            logger.info("  ✓ %s", f)
        else:
            logger.error("  ✗ %s (缺失)", f)
            all_ok = False
    return all_ok


def check_network() -> bool:
    """检查网络端口是否可用。"""
    logger.info("\n2. 检查网络端口...")
    ports_to_check = [
        ("GNSS 接收机", "0.0.0.0", 9001),
        ("IMU", "0.0.0.0", 9002),
    ]
    all_ok = True
    for name, host, port in ports_to_check:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((host, port))
            sock.close()
            logger.info("  ✓ %s 端口 %d 可用", name, port)
        except OSError as e:
            logger.error("  ✗ %s 端口 %d 被占用: %s", name, port, e)
            all_ok = False
    return all_ok


def check_database() -> bool:
    """检查数据库连接。"""
    logger.info("\n3. 检查数据库...")
    db_path = "data/ground_truth.db"
    try:
        db = GroundTruthDB(db_path)
        logger.info("  ✓ 数据库连接成功: %s", db_path)
       
        # 统计数据
        import sqlite3
        conn = sqlite3.connect(db_path)
        count_points = conn.execute("SELECT COUNT(*) FROM survey_points").fetchone()[0]
        count_patches = conn.execute("SELECT COUNT(*) FROM z_patches").fetchone()[0]
        conn.close()
       
        logger.info("    - RTK 打点记录: %d 条", count_points)
        logger.info("    - Z 轴补丁: %d 条", count_patches)
        return True
    except Exception as e:
        logger.error("  ✗ 数据库错误: %s", e)
        return False


def check_yard_map() -> bool:
    """检查堆场地图文件。"""
    logger.info("\n4. 检查堆场地图...")
    map_path = "data/yard_map.json"
    if os.path.exists(map_path):
        import json
        try:
            with open(map_path, "r") as f:
                data = json.load(f)
            b_count = len(data.get("b_matrices", {}))
            logger.info("  ✓ yard_map.json 存在，已校准堆场: %d 个", b_count)
            return True
        except Exception as e:
            logger.error("  ✗ 解析 yard_map.json 失败: %s", e)
            return False
    else:
        logger.warning("  ⚠ yard_map.json 不存在（B 车尚未校准）")
        return True  # 不存在不算错误


def check_dependencies() -> bool:
    """检查 Python 依赖包。"""
    logger.info("\n5. 检查依赖包...")
    required = ["numpy", "scipy", "yaml"]
    all_ok = True
    for pkg in required:
        try:
            __import__(pkg)
            logger.info("  ✓ %s", pkg)
        except ImportError:
            logger.error("  ✗ %s (未安装)", pkg)
            all_ok = False
    return all_ok


def main():
    setup_logging(level="INFO")
   
    logger.info("=" * 60)
    logger.info("RTG 系统诊断工具")
    logger.info("=" * 60)
    logger.info("")

    results = {
        "配置文件": check_config_files(),
        "网络端口": check_network(),
        "数据库": check_database(),
        "堆场地图": check_yard_map(),
        "依赖包": check_dependencies(),
    }

    logger.info("")
    logger.info("=" * 60)
    logger.info("诊断结果汇总")
    logger.info("=" * 60)
   
    all_passed = True
    for name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        logger.info("  %s: %s", name, status)
        if not passed:
            all_passed = False

    logger.info("")
    if all_passed:
        logger.info("✓ 系统诊断通过，可以正常运行")
        return 0
    else:
        logger.error("✗ 系统诊断发现问题，请先修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())

