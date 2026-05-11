"""
解算模块：堆场地图管理器
负责加载/保存 yard_map.json，以及识别 RTG 当前所在堆场。
"""
import json
import os
import logging
import numpy as np
from typing import Optional, Dict, Any
from src.solver.coordinate_transform import YardTransform
logger = logging.getLogger(__name__)
class YardManager:
    """
    堆场地图管理器。
    功能：
      1. 从 yard_config.yaml 构建各堆场的 YardTransform 对象
      2. 加载 yard_map.json 中已标定的 B 车变换矩阵
      3. 根据 RTG 当前 WGS84 坐标自动判断所在堆场
    """
    def __init__(self, yard_map_path: str, yard_configs: list):
        self._map_path = yard_map_path
        self._transforms: Dict[str, YardTransform] = {}
        self._b_matrices: Dict[str, Any] = {}
        self._current_yard_id: Optional[str] = None
        for yard_cfg in yard_configs:
            yid = yard_cfg["id"]
            origin = yard_cfg["origin"]
            self._transforms[yid] = YardTransform(
                origin_lat=origin["lat"],
                origin_lon=origin["lon"],
                origin_alt=origin["alt"],
                heading_deg=yard_cfg["heading_deg"],
            )
            logger.info("已加载堆场配置: %s (%s)", yid, yard_cfg.get("name", ""))
        self._load_map()
    def detect_yard(self, lat: float, lon: float) -> Optional[str]:
        """根据 WGS84 坐标判断所在堆场（取距离最近的堆场原点）。"""
        best_id = None
        best_dist = float("inf")
        for yid, tf in self._transforms.items():
            lx, ly, _ = tf.wgs84_to_lycs(lat, lon, 0.0)
            dist = (lx ** 2 + ly ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_id = yid
        if best_id and best_id != self._current_yard_id:
            logger.info("RTG 切换堆场: %s -> %s (距原点 %.1f m)",
                        self._current_yard_id, best_id, best_dist)
            self._current_yard_id = best_id
        return best_id
    def get_transform(self, yard_id=None) -> Optional[YardTransform]:
        """获取指定堆场（或当前堆场）的 YardTransform。"""
        yid = yard_id or self._current_yard_id
        return self._transforms.get(yid)
    def save_b_matrix(self, yard_id: str, M: np.ndarray) -> None:
        """保存 B 车校准矩阵并持久化到 yard_map.json。"""
        self._b_matrices[yard_id] = M
        self._save_map()
        logger.info("B 车变换矩阵已保存: 堆场 %s", yard_id)
    def get_b_matrix(self, yard_id: str) -> Optional[np.ndarray]:
        """获取指定堆场的 B 车变换矩阵，未校准返回 None。"""
        return self._b_matrices.get(yard_id)
    def _load_map(self) -> None:
        if not os.path.exists(self._map_path):
            logger.info("yard_map.json 不存在，等待标定: %s", self._map_path)
            return
        try:
            with open(self._map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for yard_id, entry in data.get("b_matrices", {}).items():
                self._b_matrices[yard_id] = np.array(entry, dtype=float)
            logger.info("已加载 yard_map.json，含 %d 个堆场矩阵", len(self._b_matrices))
        except Exception as e:
            logger.error("加载 yard_map.json 失败: %s", e)
    def _save_map(self) -> None:
        os.makedirs(os.path.dirname(self._map_path) or ".", exist_ok=True)
        data = {"b_matrices": {yid: M.tolist() for yid, M in self._b_matrices.items()}}
        try:
            with open(self._map_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("保存 yard_map.json 失败: %s", e)
