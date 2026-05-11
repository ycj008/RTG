import { Crosshair, Wifi, WifiOff, Car, Map } from 'lucide-react';
import { clsx } from 'clsx';
import { StatusBadge } from './common';
import { useAppContext } from '../context/AppContext';
import type { TabId, GnssStatus } from '../types';

interface NavbarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  gnssStatus: GnssStatus;
  isMock: boolean;
  connStatus: 'connecting' | 'connected' | 'disconnected';
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'dashboard',   label: '仪表盘' },
  { id: 'settings',    label: '工作配置' },
  { id: 'config',      label: '参数配置' },
  { id: 'mapping',     label: '场地建图' },
  { id: 'calibration', label: '车辆校准' },
  { id: 'manual',      label: '系统说明' },
];

export default function Navbar({ activeTab, onTabChange, gnssStatus, isMock, connStatus }: NavbarProps) {
  const { vehicles, yards, selectedVehicleId, selectedYardId } = useAppContext();
  const selectedVehicle = vehicles.find(v => v.vehicle_id === selectedVehicleId);
  const selectedYard    = yards.find(y => y.yard_id === selectedYardId);

  return (
    <nav className="sticky top-0 z-50 bg-slate-900/80 backdrop-blur-xl border-b border-slate-700/60 shadow-2xl">
      <div className="max-w-screen-2xl mx-auto px-6 h-16 flex items-center justify-between gap-6">
        {/* Logo */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-9 h-9 bg-blue-600/20 border border-blue-500/40 rounded-lg flex items-center justify-center">
            <Crosshair className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-widest uppercase leading-none text-white">
              RTG <span className="text-blue-400">POSITIONING</span>
            </div>
            <div className="text-[9px] text-slate-500 tracking-widest uppercase leading-none mt-0.5">
              Precision Calibration System v2.5
            </div>
          </div>
        </div>

        {/* Tab nav */}
        <div className="flex items-center gap-1 bg-slate-800/50 p-1 rounded-xl border border-slate-700/40">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={clsx(
                'tab-btn text-sm',
                activeTab === tab.id && 'tab-btn-active',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Status area */}
        <div className="flex items-center gap-3 shrink-0">
          {/* 当前车辆指示器 */}
          <button
            onClick={() => onTabChange('settings')}
            className={clsx(
              'hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border transition-colors',
              selectedVehicle
                ? 'bg-blue-900/30 border-blue-500/40 text-blue-300 hover:border-blue-400'
                : 'bg-slate-800/60 border-slate-700/60 text-slate-500 hover:border-slate-500',
            )}
            title="点击前往工作配置"
          >
            <Car className="w-3 h-3" />
            <span className="font-mono font-bold">
              {selectedVehicle ? selectedVehicle.vehicle_id : '未选车'}
            </span>
          </button>

          {/* 当前场地指示器 */}
          <button
            onClick={() => onTabChange('settings')}
            className={clsx(
              'hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border transition-colors',
              selectedYard
                ? selectedYard.mapped
                  ? 'bg-emerald-900/30 border-emerald-500/40 text-emerald-300 hover:border-emerald-400'
                  : 'bg-amber-900/30 border-amber-500/40 text-amber-300 hover:border-amber-400'
                : 'bg-slate-800/60 border-slate-700/60 text-slate-500 hover:border-slate-500',
            )}
            title="点击前往工作配置"
          >
            <Map className="w-3 h-3" />
            <span className="font-mono font-bold">
              {selectedYard ? selectedYard.yard_id : '未选场地'}
            </span>
            {selectedYard && (
              <span className={selectedYard.mapped ? 'text-emerald-400' : 'text-amber-400'}>●</span>
            )}
          </button>

          {/* WebSocket 连接状态 */}
          <button
            onClick={() => onTabChange('settings')}
            title="点击前往工作配置"
            className={clsx(
              'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border transition-colors',
              isMock
                ? 'bg-slate-800/60 border-slate-700/60 text-slate-400 hover:border-slate-500'
                : connStatus === 'connected'
                  ? 'bg-emerald-900/30 border-emerald-500/40 text-emerald-300'
                  : connStatus === 'connecting'
                    ? 'bg-amber-900/30 border-amber-500/40 text-amber-300 animate-pulse'
                    : 'bg-red-900/30 border-red-500/40 text-red-400',
            )}
          >
            {isMock ? (
              <WifiOff className="w-3.5 h-3.5" />
            ) : connStatus === 'connected' ? (
              <Wifi className="w-3.5 h-3.5" />
            ) : (
              <Wifi className="w-3.5 h-3.5 opacity-50" />
            )}
            <span className="font-bold">
              {isMock
                ? 'MOCK'
                : connStatus === 'connected'
                  ? 'LIVE'
                  : connStatus === 'connecting'
                    ? '连接中...'
                    : '已断开'}
            </span>
            {/* 连接中动画点 */}
            {!isMock && connStatus === 'connecting' && (
              <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-ping" />
            )}
            {/* 已连接呼吸点 */}
            {!isMock && connStatus === 'connected' && (
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
            )}
          </button>
          <StatusBadge status={gnssStatus} />
        </div>
      </div>
    </nav>
  );
}
