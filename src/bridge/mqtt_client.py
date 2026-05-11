"""
通信模块：MQTT 客户端
负责与后端服务的 MQTT Broker 建立连接，实现：
  1. 实时遥测数据推送（telemetry）
  2. 接收控制指令（control）
  3. 上报设备状态（status）
  4. 支持设备身份管理（初始化/注册）
"""

import json
import logging
import threading
import time
from typing import Optional, Callable, Dict, Any
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MqttClient:
    """
    MQTT 客户端封装，支持多 Topic 订阅/发布。
    
    Topic 设计：
      - rtg/{vehicle_id}/telemetry   中控机→后端：实时定位数据（10Hz）
      - rtg/{vehicle_id}/control     后端→中控机：控制指令（打点、配置更新）
      - rtg/{vehicle_id}/status      中控机→后端：健康度、场地切换等状态
      - rtg/discovery                新设备广播：设备注册请求
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int = 1883,
        vehicle_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = 60,
    ):
        """
        :param broker_host:  MQTT Broker 地址
        :param broker_port:  MQTT Broker 端口
        :param vehicle_id:   车辆 ID（如为临时ID则通过discovery注册）
        :param username:     MQTT 认证用户名
        :param password:     MQTT 认证密码
        :param keepalive:    心跳间隔（秒）
        """
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._vehicle_id  = vehicle_id or self._generate_temp_id()
        self._keepalive   = keepalive

        # MQTT 客户端
        self._client = mqtt.Client(
            client_id=f"rtg_{self._vehicle_id}_{int(time.time())}",
            clean_session=True,
        )
        if username and password:
            self._client.username_pw_set(username, password)

        # 回调注册
        self._control_callback: Optional[Callable[[dict], None]] = None
        self._lock = threading.Lock()

        # 连接状态
        self._connected = False
        self._stop_event = threading.Event()

        # 设置 MQTT 回调
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message

        logger.info("MQTT Client 初始化完成，Vehicle ID: %s", self._vehicle_id)

    # ------------------------------------------------------------------
    # 生命周期管理
    # ------------------------------------------------------------------
    def start(self) -> None:
        """启动 MQTT 客户端，连接 Broker。"""
        try:
            self._client.connect(
                self._broker_host, 
                self._broker_port, 
                self._keepalive
            )
            self._client.loop_start()
            logger.info("MQTT 连接中: %s:%d", self._broker_host, self._broker_port)
        except Exception as e:
            logger.error("MQTT 连接失败: %s", e)
            raise

    def stop(self) -> None:
        """停止 MQTT 客户端。"""
        logger.info("MQTT Client 停止中...")
        self._stop_event.set()
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("MQTT Client 已停止")

    def is_connected(self) -> bool:
        """返回连接状态。"""
        return self._connected

    # ------------------------------------------------------------------
    # 身份管理
    # ------------------------------------------------------------------
    def update_vehicle_id(self, new_id: str) -> None:
        """
        更新车辆 ID（用于设备初始化后更新正式 ID）。
        更新后会重新订阅新 ID 的 Topic。
        """
        old_id = self._vehicle_id
        self._vehicle_id = new_id
        logger.info("Vehicle ID 更新: %s -> %s", old_id, new_id)
        
        # 取消旧订阅，订阅新 Topic
        if self._connected:
            self._client.unsubscribe(f"rtg/{old_id}/control")
            self._client.subscribe(f"rtg/{new_id}/control", qos=1)

    def get_vehicle_id(self) -> str:
        """返回当前 Vehicle ID。"""
        return self._vehicle_id

    @staticmethod
    def _generate_temp_id() -> str:
        """生成临时 ID（基于 MAC 地址）。"""
        import uuid
        mac = uuid.getnode()
        mac_str = f"{mac:012x}"[-4:]  # 取后4位
        return f"RTG-NEW-{mac_str}"

    # ------------------------------------------------------------------
    # 发布接口
    # ------------------------------------------------------------------
    def publish_telemetry(self, data: Dict[str, Any]) -> None:
        """
        发布实时遥测数据（10Hz 高频）。
        
        :param data: 定位结果字典，包含 gantry/trolley 数据
        """
        topic = f"rtg/{self._vehicle_id}/telemetry"
        payload = json.dumps(data, ensure_ascii=False)
        try:
            result = self._client.publish(topic, payload, qos=0)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.warning("遥测数据发布失败: rc=%d", result.rc)
        except Exception as e:
            logger.exception("发布遥测数据异常: %s", e)

    def publish_status(self, status_data: Dict[str, Any]) -> None:
        """
        发布设备状态（低频，事件驱动）。
        
        :param status_data: 状态字典，如堆场切换、健康度等
        """
        topic = f"rtg/{self._vehicle_id}/status"
        payload = json.dumps(status_data, ensure_ascii=False)
        try:
            self._client.publish(topic, payload, qos=1)
            logger.info("设备状态已发布: %s", status_data.get("event", "unknown"))
        except Exception as e:
            logger.exception("发布状态异常: %s", e)

    def publish_discovery(self, device_info: Dict[str, Any]) -> None:
        """
        发布设备发现消息（未初始化设备广播）。
        
        :param device_info: 设备信息，包含 MAC、临时 ID 等
        """
        topic = "rtg/discovery"
        payload = json.dumps(device_info, ensure_ascii=False)
        try:
            self._client.publish(topic, payload, qos=1)
            logger.info("设备发现消息已广播: %s", device_info)
        except Exception as e:
            logger.exception("发布发现消息异常: %s", e)

    # ------------------------------------------------------------------
    # 订阅接口
    # ------------------------------------------------------------------
    def set_control_callback(self, callback: Callable[[dict], None]) -> None:
        """
        设置控制指令回调函数。
        
        :param callback: 回调函数，接收解析后的 dict
        """
        with self._lock:
            self._control_callback = callback

    # ------------------------------------------------------------------
    # MQTT 事件回调
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT 连接回调。"""
        if rc == 0:
            self._connected = True
            logger.info("✓ MQTT 已连接: %s:%d", self._broker_host, self._broker_port)
            
            # 订阅控制指令 Topic
            control_topic = f"rtg/{self._vehicle_id}/control"
            client.subscribe(control_topic, qos=1)
            logger.info("订阅控制 Topic: %s", control_topic)
        else:
            self._connected = False
            logger.error("✗ MQTT 连接失败: rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc):
        """MQTT 断连回调。"""
        self._connected = False
        if rc != 0:
            logger.warning("MQTT 意外断开: rc=%d，将自动重连", rc)
        else:
            logger.info("MQTT 正常断开")

    def _on_message(self, client, userdata, msg):
        """MQTT 消息回调（处理控制指令）。"""
        try:
            # 解析控制指令
            payload = json.loads(msg.payload.decode("utf-8"))
            logger.info("收到 MQTT 消息 [%s]: %s", msg.topic, payload)
            
            # 调用控制回调
            with self._lock:
                if self._control_callback:
                    self._control_callback(payload)
                else:
                    logger.warning("控制指令无处理器: %s", payload)
        except json.JSONDecodeError as e:
            logger.error("MQTT 消息解析失败: %s", e)
        except Exception as e:
            logger.exception("处理 MQTT 消息异常: %s", e)


