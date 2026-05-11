// ===== WebSocket 推送数据类型 =====
export type GnssStatus = 'fix' | 'float' | 'no_signal';

export interface GpsCoord {
  lat: number;
  lon: number;
  alt: number;
}

export interface LocalCoord {
  x: number;
  y: number;
  z: number;
}

/** 大车定位输出（6.1 节） */
export interface GantryData {
  /** 电气房侧中心距堆场原点的坐标 (m) */
  elec_center: { x: number; y: number };
  /** 柴油机侧中心距堆场原点的坐标 (m) */
  diesel_center: { x: number; y: number };
  /** 四个门腿中心点相对跑道中心线的偏移量 (m)，正值偏向堆场外，负值偏向堆场内 */
  leg_offsets: { fl: number; fr: number; rl: number; rr: number };
  /** 大车运行速度 (m/s)，数值增大方向为正 */
  speed: number;
}

/** 小车定位输出（6.2 节） */
export interface TrolleyData {
  /** 小车 A 端天线在 RTG 坐标系下的实时坐标 (m) */
  ant_a: LocalCoord;
  /** 小车 B 端天线在 RTG 坐标系下的实时坐标 (m) */
  ant_b: LocalCoord;
  /** 小车距轨道起始点的实际运行距离 (m) */
  travel: number;
  /** 小车运行速度 (m/s)，数值增大方向为正 */
  speed: number;
}

export interface RealtimeData {
  timestamp: string;
  gps_coord: GpsCoord;
  local_coord: LocalCoord;
  heading: number;
  roll: number;
  pitch: number;
  speed: number;
  status: GnssStatus;
  receivers: ReceiverStatus[];
  /** 大车定位数据（双中心 + 四门腿偏移 + 速度） */
  gantry: GantryData;
  /** 小车定位数据（两端天线坐标 + 行程 + 速度） */
  trolley: TrolleyData;
}

export interface ReceiverStatus {
  id: string;
  label: string;
  position: string;
  status: GnssStatus;
  satellites: number;
  hdop: number;
}

// ===== 车辆参数类型 =====
export interface AntennArm {
  id: string;
  label: string;
  dx: number;
  dy: number;
  dz: number;
}

/** 车辆物理几何参数（与场地角色无关，角色由场地是否建图决定） */
export interface VehicleProfile {
  vehicle_id: string;
  label: string;       // 用户可读名称，如 "RTG 01号机"
  height: number;
  span: number;
  antennas: AntennArm[];
}

/**
 * 后端服务连接配置（全局唯一）
 * 架构：前端 <-> 后端(WebSocket) <-> MQTT Broker <-> 中控机
 * 前端通过 ws://host:port/ws/realtime?vehicle_id=xxx 订阅指定车辆的实时数据
 */
export interface BackendConfig {
  host: string;   // 后端服务 IP，如 "192.168.1.200"
  port: number;   // 后端 WS 端口，如 8080
}

// ===== 测绘数据类型 =====
export interface SurveyPoint {
  id: string;
  bay_id: string;
  yard_id: string;
  lat: number;
  lon: number;
  alt: number;
  dz: number;
  timestamp: string;
  synced: boolean;
}

export interface YardInfo {
  yard_id: string;
  name: string;
  origin_lat: number;
  origin_lon: number;
  heading: number;
  total_bays: number;
  mapped: boolean;      // 是否已完成场地底图测绘
}

// ===== 校准数据类型 =====
export interface CalibrationStep {
  step: 1 | 2 | 3;
  bay_id: string;
  status: 'waiting' | 'in_progress' | 'done';
  measured?: LocalCoord;
  reference?: LocalCoord;
  delta?: LocalCoord;
}

// ===== API 响应类型 =====
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
}

export type TabId = 'dashboard' | 'settings' | 'config' | 'mapping' | 'calibration' | 'manual';
