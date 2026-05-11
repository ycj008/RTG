"""
通信模块：后端 HTTP API 客户端
封装与后端服务的 REST API 交互
"""

import logging
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class ApiClient:
    """后端 API 客户端"""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        logger.info("API Client 初始化: %s", self._base_url)

    def get_vehicle_config(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """获取车辆配置"""
        url = f"{self._base_url}/api/vehicle/config"
        try:
            resp = self._session.get(url, params={"vehicle_id": vehicle_id}, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception as e:
            logger.error("获取车辆配置失败: %s", e)
            return None

    def update_vehicle_config(self, vehicle_id: str, config: Dict[str, Any]) -> bool:
        """更新车辆配置"""
        url = f"{self._base_url}/api/vehicle/config"
        try:
            resp = self._session.post(url, json={"vehicle_id": vehicle_id, **config}, timeout=self._timeout)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("更新车辆配置失败: %s", e)
            return False

    def get_all_yards(self) -> List[Dict[str, Any]]:
        """获取所有堆场"""
        url = f"{self._base_url}/api/yard/all_origins"
        try:
            resp = self._session.get(url, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error("获取堆场列表失败: %s", e)
            return []

    def get_yard_map(self, yard_id: str, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """获取堆场地图"""
        url = f"{self._base_url}/api/yard/map"
        try:
            resp = self._session.get(url, params={"yard_id": yard_id, "vehicle_id": vehicle_id}, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("获取堆场地图失败: %s", e)
            return None

    def save_yard_map(self, yard_id: str, vehicle_id: str, m_matrix: List[List[float]], map_data: Optional[Dict] = None) -> bool:
        """保存堆场地图"""
        url = f"{self._base_url}/api/yard/save_map"
        payload = {"yard_id": yard_id, "vehicle_id": vehicle_id, "m_matrix": m_matrix, "map_data": map_data or {}}
        try:
            resp = self._session.post(url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("保存堆场地图失败: %s", e)
            return False

    def confirm_survey_point(self, vehicle_id: str, yard_id: str, bay_id: str, mode: str) -> Optional[Dict[str, Any]]:
        """确认打点"""
        url = f"{self._base_url}/api/survey/confirm"
        payload = {"vehicle_id": vehicle_id, "yard_id": yard_id, "bay_id": bay_id, "mode": mode}
        try:
            resp = self._session.post(url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("打点确认失败: %s", e)
            return None

    def health_check(self) -> bool:
        """健康检查"""
        try:
            resp = self._session.get(f"{self._base_url}/api/health", timeout=3.0)
            return resp.status_code == 200
        except:
            return False

