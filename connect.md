RTG 高精度定位系统交互设计 (多机扩展版)

1. 身份赋予机制 (Registration & Identity)
为了支持几十台 RTG 的快速部署，采用“前端命名-后端下发-本地持久化”的机制：
临时身份：新中控机出厂默认以 RTG-NEW-[MAC地址] 为临时 ID 连接 MQTT。
身份证号 (Vehicle ID)：用户在前端输入参数并命名（如 RTG-001）。
本地固化：中控机接收到配置后，将 vehicle_id 写入本地 config/system.yaml，从此拥有永久身份证，重启不丢失。

2. 第一阶段：设备初始化注册 (Initial Commissioning)
这是新设备第一次进入系统时的流程。
步骤            参与方                                    动作描述
1               中控机              首次启动，读取 MAC 地址，以 RTG-NEW-XXXX 身份上线 MQTT。
2               前端                    在“待选设备”列表中发现新设备，用户点击“初始化”。
3               前端            用户输入车型静态参数 ($L_{arm}, H, W_{span}$) 并赋予正式名称（如 RTG-001）。
4               后端                记录该车信息，通过 MQTT 发送 CMD_INIT_IDENTITY 指令给临时 ID。
5               中控机          收到指令，执行 save_to_local()，将 ID 和参数写入 system.yaml 并重启服务。
6               中控机                重启后：以新 ID RTG-001 重新上线，从此具备正式身份。

3. 第二阶段：日常启动与自发现 (Startup & Auto-Discovery)
设备完成注册后的日常启动逻辑。
步骤            动作类型                                                    描述
1               身份声明                            中控机读取本地 system.yaml 里的正式 ID，连接 MQTT。
2               配置对齐                中控机向后端发送 GET /api/vehicle/config?id={id} 确认参数是否有远程修改（以云端为准）。
3               堆场感知                        请求 GET /api/yard/all_origins，对比当前 GNSS 坐标，自动匹配所在堆场。
4               状态汇报                      汇报：{"current_yard": "yard_01", "mode": "working", "calibrated": true}。

4. 第三阶段：场地判定与角色分配 (Role Assignment)
后端根据 vehicle_id 和 yard_id 的历史记录判定当前任务：
角色 A (Surveyor)：该场地在 DB 中没有 M 矩阵（即没有 A 车来过）。
角色 B (Calibrator)：有底图，但该 vehicle_id 在该场地没校准过。
角色 C (Worker)：该 vehicle_id 在该场地已完成校准，直接进入高频作业模式。

5. 第四阶段：建图与校准流程 (Survey & Calibration)
核心原则：计算在端（中控机），存证在云（后端）。
打点确认：前端点击“到达贝位”，后端转发真值给中控机。
本地解算：中控机捕获高频数据，对比真值，计算偏差。
矩阵生成：所有点完成后，中控机本地执行 SVD 求解 $M$ 矩阵。
结果入库：中控机将 $M$ 矩阵提交给后端。后端标记：“场地 X 的底图已由 A 车生成” 或 “B 车已完成校准”。

6. MQTT 协议定义（带身份路由）
注册流：rtg/discovery（新设备广播身份）。
实时流：rtg/{vehicle_id}/telemetry（中控机推送实时坐标）。
控制链：rtg/{vehicle_id}/control（后端下发打点指令/配置更新）。
状态链：rtg/{vehicle_id}/status（中控机汇报健康度/当前场地）。

7. 职责总结
前端 (React)
命名与初始化：作为“入场引导”，为新设备分配 ID。
实时看板：根据 vehicle_id 订阅对应数据，在底图上实时绘图。

后端 (Backend)
身份中心：维护 ID 与 MAC 地址的映射，确保存储的数据（参数、矩阵）都能通过 ID 索引。
真值中转：根据打点动作，将数据库里的真值精准推送到对应 ID 的中控机。
中控机 (Python Core)
持久化存储：负责将后端下发的“身份证”保存到本地硬盘。
自主解算：利用本地存储的 ID 和参数，完成从 GNSS 原始信号到 LYCS 坐标的全过程。



RTG 高精度定位系统接口定义文档 (V2.0)

1. 车辆管理与初始化 (Vehicle & Identity)
1.1 获取在线车辆列表
接口: GET /api/vehicle/list
说明: 前端获取当前所有在线（含待初始化）的设备。
返回数据:
{
  "code": 200,
  "data": [
    {
      "vehicle_id": "RTG-001",
      "mac": "00:0c:29:4f:8b:35",
      "status": "online",
      "is_initialized": true,
      "last_seen": "2026-05-11 10:00:00"
    },
    {
      "vehicle_id": "RTG-NEW-8b36",
      "mac": "00:0c:29:4f:8b:36",
      "status": "online",
      "is_initialized": false
    }
  ]
}

1.2 设备初始化与重命名
接口: POST /api/vehicle/init
说明: 前端为新发现的设备分配正式 ID 并写入静态参数。
请求体:
{
  "temp_id": "RTG-NEW-8b36",
  "new_vehicle_id": "RTG-002",
  "params": {
    "l_arm": [1.5, 0.5, 3.2],
    "h": 22.5,
    "w_span": 23.47
  }
}

1.3 获取/修改车型参数
接口: GET/POST /api/vehicle/config
参数: ?vehicle_id=RTG-001
数据结构:
{
  "l_arm": [1.5, 0.5, 3.2], // 杆臂向量 [x, y, z]
  "h": 22.5,                // 吊具基准高度
  "w_span": 23.47,          // 跨距
  "ekf_params": { ... }      // 可选：算法高级参数
}

2. 堆场与地图管理 (Yard & Map)
2.1 获取所有堆场原点 (用于自发现)
接口: GET /api/yard/all_origins
说明: 中控机启动后拉取，用于对比距离自动匹配场地。
返回数据:
[
  { "yard_id": "yard_01", "name": "东区1号堆场", "origin": [22.123, 114.456] },
  { "yard_id": "yard_02", "name": "西区2号堆场", "origin": [22.125, 114.459] }
]

2.2 获取堆场底图与M矩阵
接口: GET /api/yard/map
参数: ?yard_id=yard_01&vehicle_id=RTG-01
说明: 获取该场地的 SVD 转换矩阵。若该车未校准，m_matrix 可能为空。
返回数据:
{
  "yard_id": "yard_01",
  "m_matrix": [[...], [...], [...]], // 3x3 旋转平移矩阵
  "has_base_map": true,
  "calibration_status": "none|calibrated"
}

2.3 保存解算结果 (中控机调用)
接口: POST /api/yard/save_map
说明: A车建图完成后，中控机将计算好的 M 矩阵上传。
请求体:
{
  "yard_id": "yard_01",
  "vehicle_id": "RTG-01",
  "m_matrix": [[...]], 
  "map_data": { "bays": [...] } // 场地底图元数据
}

3. 打点与校准控制 (Survey & Calibration)
3.1 确认到达贝位 (打点)
接口: POST /api/survey/confirm
说明: 前端用户点击按钮，后端匹配真值。
请求体:
{
  "vehicle_id": "RTG-01",
  "yard_id": "yard_01",
  "bay_id": "1",
  "mode": "A" // A: 建图打点, B: 校准验证
}

3.2 校准状态终审
接口: POST /api/survey/finalize
说明: 3点校准通过后，正式标记该车在场地的可用性。

4. MQTT 实时消息协议 (Real-time Flow)
4.1 实时高频坐标流 (Telemetry)
Topic: rtg/{vehicle_id}/telemetry
频率: 10Hz
Payload:
{
  "ts": 1715395200000,
  "pos": { "x": 12.34, "y": 45.67, "z": 1.23 },
  "heading": 90.5,
  "status": "fix", // fix, float, single
  "diff": { "dx": 0.02, "dy": -0.01 } // 打点时的实时残差
}

4.2 控制指令链 (Control)
Topic: rtg/{vehicle_id}/control
Payload:
{
  "cmd": "RECORD_POINT", // RECORD_POINT, UPDATE_CONFIG, START_SVD
  "data": {
    "truth": [12.33, 45.68, 1.20], // 后端下发的真值
    "bay_id": "1"
  }
}

4.3 状态汇报链 (Status)
Topic: rtg/{vehicle_id}/status
Payload:
{
  "mode": "survey|calibrate|work",
  "current_yard": "yard_01",
  "hardware": { "gnss": "ok", "imu": "ok", "plc": "connected" }
}

5. 数据类型定义汇总
类型名称                    基础格式                              说明
Matrix3x3                 number[][]                    3行3列数组，用于旋转平移矩阵
Vector3             [number, number, number]              三维空间向量 (x, y, z)
VehicleID                   string                        唯一标识符，如 "RTG-001"
GPSPoint               [number, number]                       [经度, 纬度]
StatusEnum                  string                "fix" (固定解), "float" (浮动解), "none" (无信号)