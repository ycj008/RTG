import { useState, useRef } from 'react';
import { MapPin, CheckCircle, Clock, Loader, AlertTriangle, RefreshCw } from 'lucide-react';
import { logger } from '../utils/logger';
import { SectionHeader, showToast } from './common';
import { useAppContext } from '../context/AppContext';
import type { SurveyPoint, RealtimeData } from '../types';

interface MappingProps {
  liveData: RealtimeData;
}

const SAMPLE_POINTS: SurveyPoint[] = [
  {
    id: '1',
    bay_id: 'Bay_01',
    yard_id: 'yard_01',
    lat: 22.1234567,
    lon: 114.2345678,
    alt: 12.345,
    dz: 0.012,
    timestamp: '2026-05-09T08:30:00Z',
    synced: true,
  },
  {
    id: '2',
    bay_id: 'Bay_02',
    yard_id: 'yard_01',
    lat: 22.1235021,
    lon: 114.2347211,
    alt: 12.333,
    dz: -0.008,
    timestamp: '2026-05-09T08:35:00Z',
    synced: true,
  },
];

export default function Mapping({ liveData }: MappingProps) {
  const { yards, selectedVehicleId, selectedYardId, backendConfig } = useAppContext();
  const selectedYard = yards.find(y => y.yard_id === selectedYardId) ?? null;

  const [points, setPoints] = useState<SurveyPoint[]>(SAMPLE_POINTS);
  const [bayId, setBayId] = useState('Bay_03');
  const yardId = selectedYard?.yard_id ?? 'yard_01';
  const [sampling, setSampling] = useState(false);
  const [forceRemap, setForceRemap] = useState(false);
  const samplesRef = useRef<RealtimeData[]>([]);

  const baseUrl = `http://${backendConfig.host}:${backendConfig.port}`;

  // 5s 采样均值 → POST /api/survey/confirm (mode: "A")
  const handleRecord = async () => {
    if (sampling) return;
    setSampling(true);
    samplesRef.current = [];

    const ticker = setInterval(() => {
      samplesRef.current.push({ ...liveData });
    }, 200);

    await new Promise((r) => setTimeout(r, 5000));
    clearInterval(ticker);

    const samples = samplesRef.current;
    const avgLat = samples.reduce((s, d) => s + d.gps_coord.lat, 0) / samples.length;
    const avgLon = samples.reduce((s, d) => s + d.gps_coord.lon, 0) / samples.length;
    const avgAlt = samples.reduce((s, d) => s + d.gps_coord.alt, 0) / samples.length;

    const newPoint: SurveyPoint = {
      id: String(Date.now()),
      bay_id: bayId,
      yard_id: yardId,
      lat: avgLat,
      lon: avgLon,
      alt: avgAlt,
      dz: 0,
      timestamp: new Date().toISOString(),
      synced: false,
    };

    const confirmPayload = { vehicle_id: selectedVehicleId, yard_id: yardId, bay_id: bayId, mode: 'A' };
    logger.info('Mapping', `POST /api/survey/confirm`, confirmPayload);
    try {
      // §3.1 打点确认：前端只通知后端，后端转发真值给中控机
      const res = await fetch(`${baseUrl}/api/survey/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(confirmPayload),
      });
      if (res.ok) {
        logger.info('Mapping', `打点确认成功 bayId=${bayId}`);
        newPoint.synced = true;
      } else {
        logger.warn('Mapping', `打点确认返回 HTTP ${res.status}`);
      }
    } catch (e) {
      logger.error('Mapping', '打点确认请求失败（离线暂存）', e);
    }

    setPoints((prev) => [newPoint, ...prev]);
    showToast(`✅ 已打点贝位 ${bayId}，等待中控机采集（${samples.length} 帧均值）`);
    setSampling(false);

    // 自动递增贝位号
    const match = bayId.match(/(\D+)(\d+)/);
    if (match) setBayId(`${match[1]}${String(parseInt(match[2]) + 1).padStart(2, '0')}`);
  };
  // 说明：底图（M矩阵）由中控机本地 SVD 解算后自行上传 POST /api/yard/save_map
  // 前端只负责发送打点确认，不做本地生成底图操作

  const unsyncedCount = points.filter((p) => !p.synced).length;

  // ── 未选择场地时的提示 ──
  if (!selectedYard) {
    return (
      <div className="animate-fade-in flex items-center justify-center min-h-[60vh]">
        <div className="card p-12 max-w-md w-full text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto" />
          <h2 className="text-xl font-bold text-white">未选择作业场地</h2>
          <p className="text-slate-400 text-sm">请前往「工作配置」页面选择当前场地后，再进行场地建图。</p>
        </div>
      </div>
    );
  }

  // ── 场地已建图警告（可强制重建） ──
  if (selectedYard.mapped && !forceRemap) {
    return (
      <div className="animate-fade-in flex items-center justify-center min-h-[60vh]">
        <div className="card p-12 max-w-md w-full text-center space-y-4">
          <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/30 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle className="w-8 h-8 text-emerald-400" />
          </div>
          <h2 className="text-xl font-bold text-white">{selectedYard.name} 已建图</h2>
          <p className="text-slate-400 text-sm">
            该场地底图已存在。若需要为其它车辆校准，请前往「车辆校准」页面；
            若底图数据有误，可强制重新建图（将覆盖原有数据）。
          </p>
          <button
            onClick={() => setForceRemap(true)}
            className="btn-secondary flex items-center gap-2 mx-auto"
          >
            <RefreshCw className="w-4 h-4" />
            强制重新建图
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in space-y-5">
      <SectionHeader
        title={`场地建图 · ${selectedYard.name}`}
        subtitle={`为「${selectedYard.name}」逐贝位打点确认，后端将真值转发给中控机。中控机完成 SVD 解算后自动上传底图，无需前端手动操作。`}
      >
        {unsyncedCount > 0 && (
          <span className="text-[11px] text-amber-400 bg-amber-900/30 border border-amber-500/30 px-3 py-1.5 rounded-lg">
            {unsyncedCount} 个贝位待同步（离线暂存）
          </span>
        )}
      </SectionHeader>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        {/* Control panel */}
        <div className="space-y-4">
          {/* Record card */}
          <div className="card p-5 space-y-4">
            <div>
              <label className="section-title block mb-1.5">堆场 ID</label>
              <input
                className="input-field font-mono"
                value={yardId}
                readOnly
              />
            </div>
            <div>
              <label className="section-title block mb-1.5">贝位编号</label>
              <input
                className="input-field font-mono text-2xl text-blue-400 py-3"
                value={bayId}
                onChange={(e) => setBayId(e.target.value)}
              />
            </div>

            {/* Live status */}
            <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-700/40 space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">当前 LAT</span>
                <span className="font-mono text-slate-300">{liveData.gps_coord.lat.toFixed(7)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">当前 LON</span>
                <span className="font-mono text-slate-300">{liveData.gps_coord.lon.toFixed(7)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">GNSS 状态</span>
                <span className={liveData.status === 'fix' ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                  {liveData.status === 'fix' ? 'RTK FIXED ✓' : 'FLOAT'}
                </span>
              </div>
            </div>

            <button
              onClick={handleRecord}
              disabled={sampling || liveData.status === 'no_signal'}
              className="w-full py-4 rounded-xl font-bold text-base transition-all duration-150 shadow-lg flex items-center justify-center gap-2
                disabled:opacity-50 disabled:cursor-not-allowed
                bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white shadow-emerald-900/30"
            >
              {sampling ? (
                <>
                  <Loader className="w-5 h-5 animate-spin" />
                  5s 均值采样中...
                </>
              ) : (
                <>
                  <MapPin className="w-5 h-5" />
                  采集并记录位置
                </>
              )}
            </button>

            {sampling && (
              <div className="w-full bg-slate-700 rounded-full h-1.5 overflow-hidden">
                <div className="bg-emerald-500 h-full animate-pulse" style={{ width: '70%' }} />
              </div>
            )}
          </div>

          {/* Tip box */}
          <div className="p-4 bg-blue-900/10 border border-blue-500/20 rounded-xl">
            <p className="text-[10px] font-bold text-blue-400 uppercase mb-2">作业提示</p>
            <p className="text-xs text-blue-200/60 leading-relaxed">
              请确保左门腿中心线与地面贝位线完全对齐后再触发采集。系统会自动记录 Z 轴残差作为地形补丁存储。
            </p>
          </div>

          {/* Stats */}
          <div className="card p-4 grid grid-cols-2 gap-3">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-400">{points.length}</div>
              <div className="section-title mt-1">已打点</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-emerald-400">{points.filter((p) => p.synced).length}</div>
              <div className="section-title mt-1">已同步</div>
            </div>
          </div>
        </div>

        {/* Data table */}
        <div className="lg:col-span-3 card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-700/30 border-b border-slate-700/60">
                <tr>
                  {['贝位编号', 'WGS84 坐标 (Lat / Lon)', '高度 (m)', 'Z 补偿 (m)', '采集时间', '状态'].map((h) => (
                    <th key={h} className="px-4 py-3 section-title whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {points.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-slate-700/40 hover:bg-slate-700/20 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono font-bold text-white">{p.bay_id}</td>
                    <td className="px-4 py-3 font-mono text-slate-300 text-xs">
                      {p.lat.toFixed(7)}, {p.lon.toFixed(7)}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-400">{p.alt.toFixed(3)}</td>
                    <td className={`px-4 py-3 font-mono font-bold ${p.dz >= 0 ? 'text-blue-400' : 'text-amber-400'}`}>
                      {p.dz >= 0 ? '+' : ''}{p.dz.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(p.timestamp).toLocaleTimeString('zh-CN')}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {p.synced ? (
                        <span className="badge badge-fix">
                          <CheckCircle className="w-3 h-3" />
                          已同步
                        </span>
                      ) : (
                        <span className="badge bg-amber-900/30 text-amber-400 border-amber-500/30">
                          本地
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
