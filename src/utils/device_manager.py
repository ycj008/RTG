"""
工具模块：设备身份管理
负责：
  1. 生成/读取设备 ID（vehicle_id）
  2. 设备初始化后的配置持久化
  3. 启动时的配置对齐（云端配置优先）
"""

import os
import uuid
import logging
import yaml
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DeviceManager:
    """
    设备管理器：处理设备身份初始化、配置同步等。
    
    工作流程：
      1. 读取本地 system.yaml 中的 vehicle_id
      2. 若为 null，生成临时 ID（RTG-NEW-xxxx）
      3. 等待后端下发正式 ID 后，保存到本地并重启
    """

    def __init__(self, config_path: str = "config/system.yaml"):
        """
        :param config_path: system.yaml 配置文件路径
        """
        self._config_path = config_path
        self._vehicle_id: Optional[str] = None
        self._is_initialized: bool = False
        self._mac_address: str = self._get_mac_address()

        logger.info("DeviceManager 初始化，MAC: %s", self._mac_address)

    def load_vehicle_id(self) -> str:
        """
        从配置文件加载 vehicle_id。
        若未初始化，返回临时 ID（RTG-NEW-xxxx）。
        
        :return: vehicle_id（正式或临时）
        """
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            vid = data.get("vehicle_id")
            if vid and isinstance(vid, str) and not vid.startswith("RTG-NEW"):
                # 已初始化：使用正式 ID
                self._vehicle_id = vid
                self._is_initialized = True
                logger.info("✓ 设备已初始化，Vehicle ID: %s", vid)
            else:
                # 未初始化：生成临时 ID
                self._vehicle_id = self._generate_temp_id()
                self._is_initialized = False
                logger.warning("⚠ 设备未初始化，使用临时 ID: %s", self._vehicle_id)

            return self._vehicle_id

        except FileNotFoundError:
            logger.error("配置文件不存在: %s", self._config_path)
            self._vehicle_id = self._generate_temp_id()
            self._is_initialized = False
            return self._vehicle_id
        except Exception as e:
            logger.exception("加载配置失败: %s", e)
            self._vehicle_id = self._generate_temp_id()
            self._is_initialized = False
            return self._vehicle_id

    def save_vehicle_id(self, new_vehicle_id: str) -> bool:
        """
        将正式 vehicle_id 写入配置文件（设备初始化后调用）。
        
        :param new_vehicle_id: 后端下发的正式 ID
        :return: 成功返回 True
        """
        try:
            # 读取现有配置
            if os.path.exists(self._config_path):
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {}

            # 更新 vehicle_id
            data["vehicle_id"] = new_vehicle_id

            # 写回文件
            os.makedirs(os.path.dirname(self._config_path) or ".", exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)

            self._vehicle_id = new_vehicle_id
            self._is_initialized = True

            logger.info("✓ Vehicle ID 已保存到本地: %s", new_vehicle_id)
            return True

        except Exception as e:
            logger.exception("保存 Vehicle ID 失败: %s", e)
            return False

    def is_initialized(self) -> bool:
        """返回设备是否已初始化。"""
        return self._is_initialized

    def get_vehicle_id(self) -> Optional[str]:
        """返回当前 vehicle_id。"""
        return self._vehicle_id

    def get_mac_address(self) -> str:
        """返回 MAC 地址（用于唯一标识）。"""
        return self._mac_address

    def get_device_info(self) -> Dict[str, Any]:
        """
        返回设备信息字典（用于发现广播）。
        
        :return: {temp_id, mac, is_initialized, ...}
        """
        return {
            "temp_id": self._vehicle_id,
            "mac": self._mac_address,
            "is_initialized": self._is_initialized,
            "timestamp": None,  # 由调用方填充
        }

    @staticmethod
    def _get_mac_address() -> str:
        """获取本机 MAC 地址（格式化为 xx:xx:xx:xx:xx:xx）。"""
        mac = uuid.getnode()
        mac_hex = f"{mac:012x}"
        return ":".join(mac_hex[i:i+2] for i in range(0, 12, 2))

    def _generate_temp_id(self) -> str:
        """生成临时 ID（基于 MAC 地址后4位）。"""
        mac_suffix = self._mac_address.replace(":", "")[-4:]
        return f"RTG-NEW-{mac_suffix}"


