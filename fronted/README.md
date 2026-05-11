# RTG 高精度定位管理系统 - 前端

## 项目简介

基于 React + TypeScript + Vite 的 RTG（轨道吊）定位系统管理前端，提供实时数据监控、场地建图、车辆校准等功能。

## 技术栈

- **框架**: React 18.3
- **语言**: TypeScript 5.5
- **构建工具**: Vite 5.4
- **样式**: Tailwind CSS 3.4
- **图表**: Recharts 2.12
- **图标**: Lucide React
- **实时通信**: WebSocket

## 功能模块

### 1. 仪表盘 (Dashboard)
- 实时 GPS/本地坐标显示
- 姿态数据（航向、俯仰、横滚）
- 位置轨迹图表
- GNSS 接收机状态监控
- RTG 门架实时可视化

### 2. 工作配置 (Settings)
- 车辆选择与管理
- 场地选择（支持多堆场）
- 后端服务连接配置
- 模拟数据模式切换
- 实时连接状态显示

### 3. 参数配置 (VehicleConfig)
- RTG 物理参数设置（高度、跨距）
- 天线杆臂向量配置（支持最多 6 根天线）
- 参数导入/导出
- 实时同步至后端数据库

### 4. 场地建图 (Mapping)
- A 车建图模式
- 实时位置采集（5 秒均值）
- 贝位坐标记录
- Z 轴补偿数据采集
- 底图数据生成与同步

### 5. 车辆校准 (Calibration)
- B 车三点标定流程
- 实时位置对比
- SVD 转换矩阵求解
- 校准结果持久化

### 6. 系统说明 (Manual)
- 系统架构说明
- 工作流程文档
- API 接口文档
- WebSocket 数据格式

## 快速开始

### 安装依赖

```bash
cd fronted
npm install
```

### 开发模式

```bash
npm run dev
```

启动后访问 `http://localhost:5173`

### 生产构建

```bash
npm run build
```

构建产物位于 `dist/` 目录

### 预览构建结果

```bash
npm run preview
```

## 架构设计

### 数据流

```
前端 (React)  <--WebSocket-->  后端服务  <--MQTT-->  中控机程序
     │                              │                      │
     │                           SQLite                GNSS/IMU
     │                        车模/底图数据              接收机
     └──────────────────实时坐标推送───────────────────────┘
```

### 状态管理

使用 Context API 进行全局状态管理：

- **AppContext**: 车辆列表、场地列表、选中状态、连接配置
- **useWebSocket**: WebSocket 连接管理、实时数据接收、自动重连

### WebSocket 通信

前端通过统一的后端服务接入：

```typescript
ws://${backendConfig.host}:${backendConfig.port}/ws/realtime?vehicle_id=${selectedVehicleId}
```

后端负责：
- 订阅对应车辆的 MQTT Topic
- 数据格式转换与验证
- 推送实时定位数据至前端

## 主要组件

| 组件名 | 文件 | 说明 |
|--------|------|------|
| App | `src/App.tsx` | 应用主入口，路由管理 |
| Navbar | `src/components/Navbar.tsx` | 顶部导航栏，状态指示 |
| Dashboard | `src/components/Dashboard.tsx` | 实时数据仪表盘 |
| Settings | `src/components/Settings.tsx` | 工作配置页面 |
| VehicleConfig | `src/components/VehicleConfig.tsx` | 车辆参数配置 |
| Mapping | `src/components/Mapping.tsx` | 场地建图页面 |
| Calibration | `src/components/Calibration.tsx` | 车辆校准页面 |
| Manual | `src/components/Manual.tsx` | 系统说明文档 |
| common | `src/components/common.tsx` | 通用组件库 |

## 配置文件

### Vite 配置 (`vite.config.ts`)

```typescript
server: {
  port: 5173,
  proxy: {
    '/api': 'http://localhost:8000',  // 后端 API 代理
    '/ws': {
      target: 'ws://localhost:8000',
      ws: true,
    },
  },
}
```

### Tailwind 配置 (`tailwind.config.js`)

自定义主题色、动画、网格背景等。

## API 接口

### HTTP REST

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/vehicle/config` | POST/GET | 车辆参数存取 |
| `/api/survey/confirm` | POST | 确认到达贝位 |
| `/api/yard/generate_map` | POST | 生成场地底图 |
| `/api/yard/map` | GET | 获取底图数据 |
| `/api/survey/finalize` | POST | 完成校准 |

### WebSocket

**订阅地址**: `ws://host:port/ws/realtime?vehicle_id=xxx`

**数据格式**:

```json
{
  "timestamp": "2026-05-11T10:30:45.123Z",
  "gps_coord": { "lat": 22.123456, "lon": 114.234567, "alt": 12.345 },
  "local_coord": { "x": 123.45, "y": 234.56, "z": 1.23 },
  "heading": 45.6,
  "roll": 0.25,
  "pitch": 0.12,
  "speed": 0.35,
  "status": "fix|float|no_signal",
  "receivers": [...]
}
```

## 开发注意事项

### 模拟数据模式

前端内置模拟数据生成器，可在无后端服务时独立开发调试：

1. 在 Settings 页面开启"模拟数据模式"
2. 系统自动生成仿真定位数据（10Hz 更新）
3. 所有功能页面均可正常使用

### 离线存储

- 建图数据优先存储至本地
- 支持服务器离线时的本地操作
- 云端同步为可选操作

### 类型安全

所有数据结构均在 `src/types/index.ts` 中定义，享受完整的 TypeScript 类型检查。

## 常见问题

### Q: WebSocket 连接失败？

**A**: 检查以下几点：
1. 后端服务是否正常运行
2. Settings 中的后端地址是否正确
3. 是否选择了有效的车辆 ID
4. 可临时开启"模拟模式"继续开发

### Q: 为什么场地建图页面不可用？

**A**: 需要满足以下条件：
1. 已在 Settings 中选择场地
2. 该场地状态为"未建图"
3. 如已建图可点击"强制重新建图"

### Q: 车辆校准要求？

**A**: 必须满足：
1. 已选择车辆和场地
2. 场地已完成建图
3. 按顺序完成 3 点采集

## 性能优化建议

1. 代码分割：使用 `React.lazy` + `Suspense` 按需加载页面组件
2. 图表优化：Recharts 仅渲染最近 60 帧数据
3. WebSocket：自动重连机制，断线时降级使用模拟数据
4. 构建优化：已配置 Vite 生产构建优化

## 项目结构

```
fronted/
├── public/
│   └── icon.svg              # 网站图标
├── src/
│   ├── components/           # React 组件
│   │   ├── Dashboard.tsx
│   │   ├── Settings.tsx
│   │   ├── VehicleConfig.tsx
│   │   ├── Mapping.tsx
│   │   ├── Calibration.tsx
│   │   ├── Manual.tsx
│   │   ├── Navbar.tsx
│   │   └── common.tsx
│   ├── context/
│   │   └── AppContext.tsx    # 全局状态管理
│   ├── hooks/
│   │   └── useWebSocket.ts   # WebSocket 自定义 Hook
│   ├── types/
│   │   └── index.ts          # TypeScript 类型定义
│   ├── App.tsx               # 应用主入口
│   ├── main.tsx              # React 挂载入口
│   └── index.css             # Tailwind CSS + 自定义样式
├── index.html                # HTML模板
├── package.json              # 依赖配置
├── vite.config.ts            # Vite 构建配置
├── tailwind.config.js        # Tailwind 配置
└── tsconfig.json             # TypeScript 配置
```

## 版本历史

- **v2.5.0** (2026-05-11)
  - ✅ 完成所有核心功能模块
  - ✅ 统一后端服务架构
  - ✅ 完善类型系统和错误处理
  - ✅ 优化 UI/UX 交互体验

## 后续计划

- [ ] 添加地图可视化（集成高德/百度地图）
- [ ] 支持历史轨迹回放
- [ ] 添加报警规则配置
- [ ] 多语言支持（中英文）
- [ ] 移动端适配

## 许可证

Private & Proprietary

