# RTG 系统快速入门指南

## 📋 前提条件

1. **硬件设备**
   - 3 台 GNSS RTK 双天线接收机（大车×2 + 小车×1）
   - 1 台 IMU 惯性测量单元
   - 工控机（Ubuntu 21.04 或 Windows）
   - PLC 控制器

2. **软件环境**
   - Python 3.9+
   - 网络连通性（UDP/IP + TCP）

## 🚀 5 分钟快速开始

### 步骤 1：安装依赖

```powershell
# 克隆/下载项目后
cd RTG
pip install -r requirements.txt
```

### 步骤 2：修改配置文件

编辑 `config/system.yaml`，设置正确的 IP 地址：

```yaml
gnss:
  receiver_a1:
    host: "192.168.1.101"  # ← 修改为实际 IP
    port: 9001
```

### 步骤 3：运行系统诊断

```powershell
python tools/diagnostic.py
```

确保所有检查项通过 ✓

### 步骤 4：启动主程序

```powershell
# 方式1：使用启动脚本（Windows）
.\run.ps1

# 方式2：直接运行
python src/main.py
```

系统启动后会显示：
```
============================================================
  RTG 高精度自动定位系统启动
============================================================
[INFO] DriverNode 启动，共 3 台 GNSS 接收机 + 1 台 IMU
[INFO] 系统启动完成，所有节点运行中
```

### 步骤 5：查看输出

- **日志文件**：`logs/rtg.log`
- **PLC 连接状态**：每 30 秒输出一次统计信息
- **定位数据**：通过 TCP 实时下发给 PLC

## 🧪 无硬件测试（模拟器模式）

如果暂时没有硬件设备，可以使用数据模拟器：

```powershell
# 终端1：启动主程序
python src/main.py

# 终端2：启动模拟器（另一个窗口）
python tools/simulator.py --scenario moving --speed 1.5
```

模拟器会生成虚拟的 GNSS + IMU 数据，主程序会正常处理并输出。

## 📐 工程实施流程

### 阶段 1：RTK 手持打点（物理底座）

测绘对象：堆场原点、贝位中心线

```powershell
# 打堆场原点
python tools/rtk_survey.py --yard yard_01 --type origin

# 打贝位（需逐个打点，1-20 号）
python tools/rtk_survey.py --yard yard_01 --type bay --bay-no 1
python tools/rtk_survey.py --yard yard_01 --type bay --bay-no 2
# ... 继续直到所有贝位
```

### 阶段 2：A 车跑车建图（动态残差修正）

A 车依次停靠在各贝位，记录 Z 轴残差：

```powershell
# 启动主程序（终端1）
python src/main.py

# A 车停靠在 1 号贝位后，运行（终端2）
python tools/build_map.py --yard yard_01 --bay 1

# 继续其他贝位...
```

### 阶段 3：B 车校准（参数继承）

B 车进场后，在前 3 个点位停靠：
1. solver_node 自动采集校准点
2. 凑够 3 点后自动计算转换矩阵 M
3. 结果保存到 `data/yard_map.json`

## 🔧 常见问题

### Q1：启动后无定位数据？

**检查：**
1. GNSS 接收机是否正确配置 UDP 输出
2. 网络地址/端口是否正确（`config/system.yaml`）
3. 防火墙是否放行端口 9001/9002

**调试：**
```powershell
# 查看日志
Get-Content logs/rtg.log -Tail 50 -Wait

# 检查端口占用
netstat -an | findstr "9001"
```

### Q2：PLC 无法连接？

**检查：**
1. PLC IP/端口配置（`config/system.yaml` 中 `plc.host`）
2. PLC 是否启动 TCP 服务器模式
3. 网络是否连通（`ping 192.168.1.200`）

### Q3：定位精度不符合要求？

**可能原因：**
1. 杆臂向量 `L_arm` 未正确标定 → 重新测量
2. Z 轴残差未补偿 → 完成 A 车建图流程
3. GNSS 信号质量差 → 检查天线安装、卫星数量

### Q4：模拟器数据无法被主程序接收？

**检查：**
1. 主程序和模拟器的 `--host` 参数是否一致
2. 端口是否被占用
3. 模拟器是否在主程序之后启动

## 📚 进阶配置

### 调整 EKF 参数

编辑 `config/vehicle_params.yaml`：

```yaml
ekf:
  sigma_pos: 0.05        # 位置过程噪声（增大=更信任 GNSS）
  sigma_vel: 0.01        # 速度过程噪声
  sigma_gnss_h: 0.03     # GNSS 量测噪声（减小=更信任 GNSS）
```

### 修改帧率

编辑 `config/system.yaml`：

```yaml
plc:
  frame_rate_hz: 20      # 提升到 20Hz（需 PLC 支持）
```

### 启用调试日志

```yaml
logging:
  level: "DEBUG"         # 输出详细调试信息
```

## 🧪 运行单元测试

```powershell
# 运行所有测试
python -m unittest discover tests

# 单独测试某个模块
python tests/test_coordinate_transform.py
python tests/test_lpoint_solver.py
python tests/test_protocol.py
```

## 📞 技术支持

- **文档**：详细工程手册见 `readme.md`
- **项目总结**：`PROJECT_SUMMARY.md`
- **诊断工具**：`python tools/diagnostic.py`

## ✨ 提示

1. **首次运行**：建议先用模拟器测试整个流程
2. **生产环境**：务必完成所有校准步骤（RTK 打点 + A 车建图）
3. **备份数据**：定期备份 `data/` 目录（包含重要标定数据）
4. **日志监控**：生产环境建议配置日志告警

---

**祝您使用愉快！**

