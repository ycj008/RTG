"""
RTG 高精度自动定位系统 - 主程序入口
启动所有功能节点（driver / fusion / solver / bridge / mqtt），监听系统信号。
"""

import sys
import signal
import logging
import time
from pathlib import Path

# 添加项目根目录到模块搜索路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logging
from src.utils.config_loader import init_config, get_config
from src.utils.database import GroundTruthDB
from src.utils.device_manager import DeviceManager
from src.driver.driver_node import DriverNode
from src.fusion.fusion_node import FusionNode
from src.solver.solver_node import SolverNode
from src.solver.yard_manager import YardManager
from src.bridge.bridge_node import BridgeNode
from src.bridge.mqtt_client import MqttClient
from src.bridge.api_client import ApiClient
from src.core.event_bus import get_bus, EventBus

logger = logging.getLogger("rtg.main")


class RTGSystem:
    """
    RTG 定位系统主控类。
    负责初始化配置、各功能节点的生命周期管理、MQTT通信、后端API对接。
    """

    def __init__(self):
        # 加载配置
        config_files = [
            "config/system.yaml",
            "config/vehicle_params.yaml",
            "config/yard_config.yaml",
        ]
        init_config(*config_files)
        cfg = get_config()

        # 初始化日志
        setup_logging(
            level=cfg.get("logging.level", "INFO"),
            log_file=cfg.get("logging.file", "logs/rtg.log"),
            max_bytes=cfg.get("logging.max_bytes", 10485760),
            backup_count=cfg.get("logging.backup_count", 5),
        )
        logger.info("=" * 60)
        logger.info("RTG 高精度自动定位系统启动")
        logger.info("=" * 60)

        # 设备管理器：加载/生成 vehicle_id
        self._device_mgr = DeviceManager()
        self._vehicle_id = self._device_mgr.load_vehicle_id()
        logger.info("当前 Vehicle ID: %s", self._vehicle_id)

        # 后端 API 客户端
        backend_url = cfg.get("backend.api_base_url", "http://localhost:8000")
        self._api_client = ApiClient(backend_url)
        
        # 启动时健康检查
        if self._api_client.health_check():
            logger.info("✓ 后端服务连接正常: %s", backend_url)
        else:
            logger.warning("⚠ 后端服务暂时不可达: %s", backend_url)

        # MQTT 客户端
        mqtt_host = cfg.get("mqtt.broker_host", "localhost")
        mqtt_port = cfg.get("mqtt.broker_port", 1883)
        self._mqtt_client = MqttClient(
            broker_host=mqtt_host,
            broker_port=mqtt_port,
            vehicle_id=self._vehicle_id,
            username=cfg.get("mqtt.username"),
            password=cfg.get("mqtt.password"),
        )
        # 设置 MQTT 控制指令回调
        self._mqtt_client.set_control_callback(self._on_mqtt_control)

        # 初始化数据库
        db_path = cfg.get("database.path", "data/ground_truth.db")
        self._db = GroundTruthDB(db_path)

        # 初始化堆场管理器
        yard_map_path = cfg.get("yard_map.path", "data/yard_map.json")
        yard_configs  = cfg.get("yards", [])
        self._yard_manager = YardManager(yard_map_path, yard_configs)

        # 事件总线
        self._bus = get_bus()

        # 初始化各功能节点
        self._driver_node = DriverNode()
        self._fusion_node = FusionNode()
        self._solver_node = SolverNode(
            yard_manager=self._yard_manager,
            db=self._db,
        )
        self._bridge_node = BridgeNode()

        # 订阅定位结果，用于 MQTT 推送
        self._bus.subscribe(EventBus.TOPIC_POSITION_RESULT, self._on_position_result)

        # 系统运行标志
        self._running = False
        self._current_yard_id = None

        # 信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def start(self) -> None:
        """启动所有节点。"""
        logger.info("启动各功能节点...")
        try:
            # 启动 MQTT
            self._mqtt_client.start()
            time.sleep(1)  # 等待 MQTT 连接

            # 如果设备未初始化，发送发现广播
            if not self._device_mgr.is_initialized():
                self._broadcast_discovery()

            # 配置对齐：从云端拉取最新配置
            if self._device_mgr.is_initialized():
                self._sync_config_from_cloud()

            # 启动驱动节点
            self._driver_node.start()
            
            # 启动通信节点
            self._bridge_node.start()
            
            self._running = True
            logger.info("系统启动完成，所有节点运行中")
            logger.info("按 Ctrl+C 停止系统")
        except Exception as exc:
            logger.exception("启动失败: %s", exc)
            self.stop()
            sys.exit(1)

    def stop(self) -> None:
        """停止所有节点。"""
        if not self._running:
            return
        logger.info("系统停止中...")
        self._running = False
        try:
            self._bridge_node.stop()
            self._driver_node.stop()
            self._mqtt_client.stop()
            logger.info("所有节点已停止")
        except Exception as exc:
            logger.exception("停止过程出错: %s", exc)

    def run_forever(self) -> None:
        """主循环（阻塞直到收到停止信号）。"""
        import time
        try:
            while self._running:
                time.sleep(1.0)
                # 定期输出统计信息（可选）
                if int(time.time()) % 30 == 0:
                    self._log_stats()
        except KeyboardInterrupt:
            logger.info("收到键盘中断")
        finally:
            self.stop()

    def _signal_handler(self, signum, frame):
        """信号处理器（SIGINT / SIGTERM）。"""
        logger.info("收到系统信号 %d，准备退出", signum)
        self._running = False

    def _log_stats(self) -> None:
        """输出系统运行统计。"""
        bridge_stats = self._bridge_node.get_stats()
        plc_connected = self._bridge_node.is_plc_connected
        mqtt_connected = self._mqtt_client.is_connected()
        logger.info(
            "系统状态 | PLC: %s | MQTT: %s | 发送帧: %d | 丢弃: %d | 错误: %d",
            "✓" if plc_connected else "✗",
            "✓" if mqtt_connected else "✗",
            bridge_stats.get("sent", 0),
            bridge_stats.get("dropped", 0),
            bridge_stats.get("errors", 0),
        )

    # ------------------------------------------------------------------
    # MQTT 相关回调
    # ------------------------------------------------------------------
    def _on_mqtt_control(self, cmd: dict) -> None:
        """
        处理 MQTT 控制指令回调。
        
        支持的指令：
          - CMD_INIT_IDENTITY:  设备初始化（临时ID→正式ID）
          - RECORD_POINT:       建图/校准打点
          - UPDATE_CONFIG:      更新车辆配置
          - START_SVD:          执行校准计算
        """
        cmd_type = cmd.get("cmd")
        logger.info("收到 MQTT 控制指令: %s", cmd_type)

        try:
            if cmd_type == "CMD_INIT_IDENTITY":
                self._handle_init_identity(cmd)
            elif cmd_type == "RECORD_POINT":
                self._handle_record_point(cmd)
            elif cmd_type == "UPDATE_CONFIG":
                self._handle_update_config(cmd)
            elif cmd_type == "START_SVD":
                self._handle_start_svd(cmd)
            else:
                logger.warning("未知控制指令: %s", cmd_type)
        except Exception as e:
            logger.exception("处理控制指令异常: %s", e)

    def _on_position_result(self, result) -> None:
        """
        订阅定位结果，推送到 MQTT（实时遥测）。
        
        :param result: PositionResult 对象
        """
        if not self._mqtt_client.is_connected():
            return

        # 转换为可序列化的字典
        telemetry = {
            "timestamp": result.timestamp,
            "yard_id": result.yard_id,
            "gantry": {
                "center_elec": result.gantry.center_elec_side,
                "center_engine": result.gantry.center_engine_side,
                "lpoint_x": result.gantry.lpoint_x,
                "lpoint_y": result.gantry.lpoint_y,
                "lpoint_z": result.gantry.lpoint_z,
                "speed": result.gantry.speed,
                "heading": result.gantry.heading,
                "leg_offsets": result.gantry.leg_offsets,
            },
            "trolley": {
                "center_x": result.trolley.center_x,
                "center_y": result.trolley.center_y,
                "center_z": result.trolley.center_z,
                "travel_distance": result.trolley.travel_distance,
                "speed": result.trolley.speed,
            },
            "status": {
                "fix_quality": result.gnss_fix_quality,
                "imu_coasting": result.imu_coasting_active,
                "imu_coasting_duration": result.imu_coasting_duration,
            },
        }

        self._mqtt_client.publish_telemetry(telemetry)

    # ------------------------------------------------------------------
    # 控制指令处理器
    # ------------------------------------------------------------------
    def _handle_init_identity(self, cmd: dict) -> None:
        """处理设备初始化指令（临时ID→正式ID）。"""
        new_vehicle_id = cmd.get("data", {}).get("new_vehicle_id")
        if not new_vehicle_id:
            logger.error("初始化指令缺少 new_vehicle_id")
            return

        # 保存到本地配置
        if self._device_mgr.save_vehicle_id(new_vehicle_id):
            # 更新 MQTT 客户端的 vehicle_id
            self._mqtt_client.update_vehicle_id(new_vehicle_id)
            self._vehicle_id = new_vehicle_id

            # 上报状态
            self._mqtt_client.publish_status({
                "event": "identity_initialized",
                "vehicle_id": new_vehicle_id,
                "timestamp": time.time(),
            })

            logger.info("✓ 设备初始化完成: %s，建议重启系统", new_vehicle_id)
        else:
            logger.error("✗ 设备初始化失败")

    def _handle_record_point(self, cmd: dict) -> None:
        """处理打点指令（建图/校准）。"""
        data = cmd.get("data", {})
        truth = data.get("truth")  # [x, y, z]
        bay_id = data.get("bay_id")

        if not truth or not bay_id:
            logger.error("打点指令参数不完整")
            return

        # TODO: 触发 solver_node 的校准点采集
        # 这里需要暂存当前位置，与真值对比
        logger.info("收到打点指令: 贝位=%s, 真值=%s", bay_id, truth)

    def _handle_update_config(self, cmd: dict) -> None:
        """处理配置更新指令。"""
        config = cmd.get("data", {})
        logger.info("收到配置更新指令: %s", config)
        # TODO: 动态更新车辆参数（需要重新加载配置）

    def _handle_start_svd(self, cmd: dict) -> None:
        """处理启动 SVD 校准计算指令。"""
        logger.info("收到 SVD 校准指令")
        # TODO: 触发 solver_node 执行 B 车校准矩阵求解

    # ------------------------------------------------------------------
    # 辅助功能
    # ------------------------------------------------------------------
    def _broadcast_discovery(self) -> None:
        """发送设备发现广播（未初始化设备）。"""
        device_info = self._device_mgr.get_device_info()
        device_info["timestamp"] = time.time()
        self._mqtt_client.publish_discovery(device_info)
        logger.info("已发送设备发现广播: %s", device_info)

    def _sync_config_from_cloud(self) -> None:
        """从云端同步配置（启动时调用）。"""
        logger.info("正在从云端同步配置...")
        try:
            config = self._api_client.get_vehicle_config(self._vehicle_id)
            if config:
                logger.info("✓ 云端配置同步成功")
                # TODO: 对比本地配置，必要时更新
            else:
                logger.warning("⚠ 云端配置获取失败，使用本地配置")
        except Exception as e:
            logger.exception("配置同步异常: %s", e)


def main():
    """主函数入口。"""
    system = RTGSystem()
    system.start()
    system.run_forever()


if __name__ == "__main__":
    main()

