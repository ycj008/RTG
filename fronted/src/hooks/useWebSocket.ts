import { useEffect, useRef, useState, useCallback } from 'react';
import type { RealtimeData } from '../types';
import { logger } from '../utils/logger';

// 空白数据（未连接时的默认占位）
const BLANK_DATA: RealtimeData = {
  timestamp: '',
  gps_coord: { lat: 0, lon: 0, alt: 0 },
  local_coord: { x: 0, y: 0, z: 0 },
  heading: 0,
  roll: 0,
  pitch: 0,
  speed: 0,
  status: 'no_signal',
  receivers: [],
  gantry: {
    elec_center: { x: 0, y: 0 },
    diesel_center: { x: 0, y: 0 },
    leg_offsets: { fl: 0, fr: 0, rl: 0, rr: 0 },
    speed: 0,
  },
  trolley: {
    ant_a: { x: 0, y: 0, z: 0 },
    ant_b: { x: 0, y: 0, z: 0 },
    travel: 0,
    speed: 0,
  },
};

// 模拟数据生成（无后端时使用）
function generateMockData(): RealtimeData {
  const now = new Date();
  const t = now.getTime() / 1000;
  const trolleyTravel = 8.5 + Math.sin(t * 0.3) * 6.0;
  return {
    timestamp: now.toISOString(),
    gps_coord: {
      lat: 22.123456 + Math.sin(t * 0.1) * 0.00001,
      lon: 114.234567 + Math.cos(t * 0.1) * 0.00001,
      alt: 12.345 + Math.sin(t * 0.3) * 0.05,
    },
    local_coord: {
      x: 123.45 + Math.sin(t * 0.2) * 0.02,
      y: 234.56 + Math.cos(t * 0.15) * 0.02,
      z: 1.23 + Math.sin(t * 0.5) * 0.01,
    },
    heading: (180.5 + Math.sin(t * 0.05) * 0.5 + 360) % 360,
    roll: 0.25 + Math.sin(t * 0.3) * 0.05,
    pitch: 0.12 + Math.cos(t * 0.4) * 0.03,
    speed: Math.abs(Math.sin(t * 0.1)) * 0.8,
    status: 'fix',
    receivers: [
      { id: 'recv1', label: 'Recv-1 (大车左前)', position: 'FL', status: 'fix', satellites: 14, hdop: 0.8 },
      { id: 'recv2', label: 'Recv-2 (大车右后)', position: 'RR', status: 'fix', satellites: 13, hdop: 0.9 },
      { id: 'recv3', label: 'Recv-3 (小车)', position: 'T',  status: 'fix', satellites: 15, hdop: 0.7 },
    ],
    gantry: {
      elec_center: {
        x: 123.45 + Math.sin(t * 0.2) * 0.02,
        y: 5.12 + Math.sin(t * 0.1) * 0.005,
      },
      diesel_center: {
        x: 123.45 + Math.sin(t * 0.2) * 0.02,
        y: -5.12 + Math.cos(t * 0.1) * 0.005,
      },
      leg_offsets: {
        fl:  0.008 + Math.sin(t * 0.3) * 0.004,
        fr: -0.012 + Math.cos(t * 0.3) * 0.004,
        rl:  0.010 + Math.sin(t * 0.4) * 0.004,
        rr: -0.009 + Math.cos(t * 0.4) * 0.004,
      },
      speed: Math.sin(t * 0.1) * 0.8,
    },
    trolley: {
      ant_a: {
        x: trolleyTravel + 0.35,
        y:  0.30 + Math.sin(t * 0.8) * 0.005,
        z: -28.50 + Math.cos(t * 0.2) * 0.015,
      },
      ant_b: {
        x: trolleyTravel - 0.35,
        y: -0.30 + Math.cos(t * 0.8) * 0.005,
        z: -28.50 + Math.cos(t * 0.2) * 0.015,
      },
      travel: trolleyTravel,
      speed: Math.cos(t * 0.3) * 0.5,
    },
  };
}

interface UseWebSocketOptions {
  /** WebSocket 完整地址，如 "ws://192.168.1.101:8000/ws/realtime"。为 null 时不尝试连接 */
  url: string | null;
  /** 强制使用模拟数据，忽略 url */
  forceMock: boolean;
}

interface UseWebSocketReturn {
  data: RealtimeData;
  /** 是否已与中控机建立真实 WebSocket 连接 */
  connected: boolean;
  /** 当前是否处于模拟数据模式 */
  isMock: boolean;
  /** 连接状态：connecting | connected | disconnected */
  connStatus: 'connecting' | 'connected' | 'disconnected';
}

export function useWebSocket({ url, forceMock }: UseWebSocketOptions): UseWebSocketReturn {
  const [data, setData] = useState<RealtimeData>(BLANK_DATA);
  const [connected, setConnected] = useState(false);
  const [connStatus, setConnStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const mockTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startMock = useCallback(() => {
    if (mockTimerRef.current) return;
    mockTimerRef.current = setInterval(() => {
      setData(generateMockData());
    }, 200);
  }, []);

  const stopMock = useCallback(() => {
    if (mockTimerRef.current) {
      clearInterval(mockTimerRef.current);
      mockTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    // 关闭已有连接
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);

    // 强制模拟模式
    if (forceMock) {
      logger.info('WebSocket', '模拟模式已启用');
      setConnStatus('disconnected');
      startMock();
      return () => { stopMock(); };
    }

    // 未指定 url（未选车辆）：停止模拟，重置为空白数据
    if (!url) {
      logger.debug('WebSocket', '未指定 URL，重置为空白数据');
      stopMock();
      setData(BLANK_DATA);
      setConnStatus('disconnected');
      return () => { stopMock(); };
    }

    // 真实连接模式
    logger.info('WebSocket', '准备连接', { url });
    stopMock();
    setConnStatus('connecting');

    let retryTimer: ReturnType<typeof setTimeout>;
    let silenceTimer: ReturnType<typeof setTimeout>;   // 静默超时检测
    let ws: WebSocket | null = null;
    let cancelled = false;

    /** 重置静默超时（每收到一帧数据就重置一次，超过 5s 无数据则主动重连） */
    const resetSilenceTimer = () => {
      clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => {
        if (cancelled) return;
        logger.warn('WebSocket', '5s 内无数据帧，主动重连（可能被代理静默断开）', { url });
        ws?.close();   // 触发 onclose → 走正常重连流程
      }, 5000);
    };

    const connect = () => {
      if (cancelled) return;
      try {
        ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (cancelled) { ws?.close(); return; }
          logger.info('WebSocket', '连接成功', { url });
          setConnected(true);
          setConnStatus('connected');
          stopMock();
          resetSilenceTimer();   // 开始计时
        };

        ws.onmessage = (e) => {
          resetSilenceTimer();   // 收到数据，重置超时
          try {
            const payload = JSON.parse(e.data) as RealtimeData;
            logger.debug('WebSocket', '收到数据帧', { ts: payload.timestamp, status: payload.status });
            setData(payload);
          } catch {
            logger.warn('WebSocket', '数据帧解析失败', { raw: e.data?.slice?.(0, 80) });
          }
        };

        ws.onerror = (ev) => {
          logger.warn('WebSocket', '连接出错，等待重连', { url, ev });
          setConnStatus('connecting');
        };

        ws.onclose = (ev) => {
          if (cancelled) return;
          clearTimeout(silenceTimer);
          logger.warn('WebSocket', `连接关闭 (code=${ev.code})，5s 后重连`, { url });
          setConnected(false);
          setConnStatus('connecting');
          retryTimer = setTimeout(connect, 5000);
        };
      } catch {
        setConnStatus('connecting');
        startMock();
        retryTimer = setTimeout(connect, 5000);
      }
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
      clearTimeout(silenceTimer);
      stopMock();
      ws?.close();
    };
  }, [url, forceMock, startMock, stopMock]);

  // isMock 仅在强制模拟时为 true；
  // url=null（未选车辆）或连接中 均属于"未连接"状态，不算模拟
  const isMock = forceMock;

  return { data, connected, isMock, connStatus };
}
