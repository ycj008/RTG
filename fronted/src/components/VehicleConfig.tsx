import { useState, useEffect } from 'react';
import { Settings2, Plus, Trash2, Save, FolderOpen, Car } from 'lucide-react';
import { SectionHeader, showToast } from './common';
import { useAppContext } from '../context/AppContext';
import type { VehicleProfile, AntennArm } from '../types';
import { clsx } from 'clsx';
import { logger } from '../utils/logger';

// ============================================================
// 天线杆臂输入行
// ============================================================
function ArmInput({
  ant,
  onChange,
  onDelete,
}: {
  ant: AntennArm;
  onChange: (id: string, key: keyof AntennArm, val: string | number) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <input
          className="input-field text-sm py-1.5 flex-1 mr-3 font-mono"
          value={ant.label}
          onChange={(e) => onChange(ant.id, 'label', e.target.value)}
          placeholder="天线标签"
        />
        <button
          onClick={() => onDelete(ant.id)}
          className="p-1.5 text-slate-500 hover:text-red-400 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {(['dx', 'dy', 'dz'] as const).map((axis) => (
          <div key={axis}>
            <label className="section-title block mb-1">
              {axis.toUpperCase()} (m)
            </label>
            <input
              type="number"
              step="0.001"
              className="input-field text-sm py-1.5 font-mono"
              value={ant[axis]}
              onChange={(e) => onChange(ant.id, axis, parseFloat(e.target.value) || 0)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// 主组件
// ============================================================
export default function VehicleConfig() {
  const { vehicles, updateVehicle, selectedVehicleId, backendConfig, useMock } = useAppContext();

  const defaultId = selectedVehicleId ?? (vehicles[0]?.vehicle_id ?? null);
  const [editId, setEditId] = useState<string | null>(defaultId);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  const baseVehicle = vehicles.find(v => v.vehicle_id === editId) ?? null;
  const [cfg, setCfg] = useState<VehicleProfile | null>(baseVehicle);

  const baseUrl = `http://${backendConfig.host}:${backendConfig.port}`;

  // 切换车辆时从后端加载最新参数（模拟模式下直接使用 context 数据，不发请求）
  useEffect(() => {
    const local = vehicles.find(v => v.vehicle_id === editId) ?? null;
    if (!editId || useMock) {
      logger.debug('VehicleConfig', `模拟模式或无 editId，使用本地数据`, { editId, useMock });
      setCfg(local);
      return;
    }
    const url = `${baseUrl}/api/vehicle/config?vehicle_id=${editId}`;
    logger.info('VehicleConfig', `GET /api/vehicle/config`, { vehicle_id: editId, url });
    setLoading(true);
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (data && local) {
          logger.info('VehicleConfig', '参数加载成功', data);
          setCfg({ ...local, ...data });
        } else {
          logger.warn('VehicleConfig', '返回数据为空，使用本地数据');
          setCfg(local);
        }
      })
      .catch((e) => {
        logger.error('VehicleConfig', '参数加载失败，fallback 到本地数据', e);
        setCfg(local);
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editId, baseUrl, useMock]);

  const handleSelectVehicle = (id: string) => {
    setEditId(id);
  };

  const handleAntChange = (id: string, key: keyof AntennArm, val: string | number) => {
    setCfg((prev) => prev ? ({
      ...prev,
      antennas: prev.antennas.map((a) => (a.id === id ? { ...a, [key]: val } : a)),
    }) : null);
  };

  const handleAddAnt = () => {
    if (!cfg) return;
    const newAnt: AntennArm = {
      id: `ant_${Date.now()}`,
      label: `Antenna ${cfg.antennas.length + 1}`,
      dx: 0, dy: 0, dz: 0,
    };
    setCfg((prev) => prev ? { ...prev, antennas: [...prev.antennas, newAnt] } : null);
  };

  const handleDelete = (id: string) => {
    setCfg((prev) => prev ? { ...prev, antennas: prev.antennas.filter((a) => a.id !== id) } : null);
  };

  const handleSave = async () => {
    if (!cfg) return;
    setSaving(true);
    updateVehicle(cfg);
    logger.info('VehicleConfig', 'POST /api/vehicle/config', { vehicle_id: cfg.vehicle_id });
    try {
      const res = await fetch(`${baseUrl}/api/vehicle/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg),
      });
      if (res.ok) {
        logger.info('VehicleConfig', `参数保存成功 vehicle_id=${cfg.vehicle_id}`);
        showToast(`✅ ${cfg.label} 参数已保存至后端数据库`);
      } else {
        logger.warn('VehicleConfig', `保存返回 HTTP ${res.status}`);
        showToast('⚠️ 保存失败，请检查后端连接', 'error');
      }
    } catch (e) {
      logger.error('VehicleConfig', '保存请求失败', e);
      showToast('⚠️ 离线模式：参数已保存至本地（模拟）', 'info');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="animate-fade-in space-y-6">
      <SectionHeader
        title="RTG 参数配置"
        subtitle="管理各车辆的物理几何参数（杆臂值、跨距、高度），用于 L-Point 刚体变换。车辆在场地中的角色（建图/校准）由场地是否已建图决定，与此处无关。"
      />

      {/* ── 车辆选择器 ── */}
      <div className="card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Car className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-bold uppercase tracking-wide text-slate-300">选择要编辑的车辆</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {vehicles.map((v) => (
            <button
              key={v.vehicle_id}
              onClick={() => handleSelectVehicle(v.vehicle_id)}
              className={clsx(
                'px-4 py-2 rounded-lg text-sm font-bold border transition-all duration-150',
                editId === v.vehicle_id
                  ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-900/30'
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500',
              )}
            >
              {v.label}
              <span className="ml-2 text-[10px] font-mono opacity-60">{v.vehicle_id}</span>
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="card p-10 flex items-center justify-center text-slate-400 gap-3">
          <FolderOpen className="w-5 h-5 animate-pulse" />
          <span>正在从后端加载参数...</span>
        </div>
      ) : cfg ? (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* 基本参数 */}
            <div className="card p-6 space-y-5">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-700/60">
                <Settings2 className="w-4 h-4 text-blue-400" />
                <span className="text-sm font-bold uppercase tracking-wide text-slate-300">基本属性</span>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="section-title block mb-1.5">车辆编号</label>
                  <input
                    className="input-field font-mono opacity-60 cursor-not-allowed"
                    value={cfg.vehicle_id}
                    readOnly
                    title="车辆编号不可修改"
                  />
                </div>
                <div>
                  <label className="section-title block mb-1.5">显示名称</label>
                  <input
                    className="input-field"
                    value={cfg.label}
                    onChange={(e) => setCfg((p) => p ? { ...p, label: e.target.value } : null)}
                    placeholder="如：RTG 01号机"
                  />
                </div>
                <div>
                  <label className="section-title block mb-1.5">标称高度 H (m)</label>
                  <input
                    type="number"
                    step="0.001"
                    className="input-field font-mono text-lg"
                    value={cfg.height}
                    onChange={(e) => setCfg((p) => p ? { ...p, height: parseFloat(e.target.value) || 0 } : null)}
                  />
                </div>
                <div>
                  <label className="section-title block mb-1.5">门腿跨距 W_span (m)</label>
                  <input
                    type="number"
                    step="0.001"
                    className="input-field font-mono text-lg"
                    value={cfg.span}
                    onChange={(e) => setCfg((p) => p ? { ...p, span: parseFloat(e.target.value) || 0 } : null)}
                  />
                </div>
              </div>

              {/* 公式说明 */}
              <div className="mt-4 p-4 bg-blue-900/10 border border-blue-500/20 rounded-xl">
                <p className="section-title mb-2">L-Point 解算公式</p>
                <p className="text-xs font-mono text-blue-300 leading-relaxed">
                  P_final = P_gps − R · L_arm
                  <br />
                  R = Rz(ψ) · Ry(θ) · Rx(φ)
                </p>
              </div>
            </div>

            {/* 天线杆臂 */}
            <div className="lg:col-span-2 card p-6">
              <div className="flex items-center justify-between pb-3 border-b border-slate-700/60 mb-5">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wide text-slate-300">
                    天线阵列杆臂值（相对 L-Point）
                  </h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    共 {cfg.antennas.length} 根天线 · 支持最多 6 根
                  </p>
                </div>
                <button
                  onClick={handleAddAnt}
                  disabled={cfg.antennas.length >= 6}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs font-bold disabled:opacity-40"
                >
                  <Plus className="w-3.5 h-3.5" />
                  添加天线
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[480px] overflow-y-auto pr-1">
                {cfg.antennas.map((ant) => (
                  <ArmInput key={ant.id} ant={ant} onChange={handleAntChange} onDelete={handleDelete} />
                ))}
              </div>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-700/60">
            <button className="btn-secondary flex items-center gap-2">
              <FolderOpen className="w-4 h-4" />
              导入配置
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-primary flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              {saving ? '保存中...' : '保存并下发至中控机'}
            </button>
          </div>
        </>
      ) : (
        <div className="card p-12 text-center text-slate-500">
          <Car className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>请先在上方选择一台车辆进行参数编辑</p>
        </div>
      )}
    </div>
  );
}
