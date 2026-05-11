import { useState, useEffect } from 'react';
import { Car, Map, CheckCircle2, AlertTriangle, Wifi, WifiOff, Loader2, ToggleLeft, ToggleRight, Edit2, X, Save, Plus, Zap, RefreshCw } from 'lucide-react';
import { SectionHeader, showToast } from './common';
import { useAppContext } from '../context/AppContext';
import type { PendingDevice } from '../context/AppContext';
import { clsx } from 'clsx';

// ── 新设备初始化弹窗 ──────────────────────────────────────
function InitDeviceModal({ device, backendBase, onClose, onDone }: {
  device: PendingDevice;
  backendBase: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const { initDevice } = useAppContext();
  const [newId, setNewId] = useState('RTG-');
  const [label, setLabel] = useState('');
  const [lArmX, setLArmX] = useState('1.5');
  const [lArmY, setLArmY] = useState('0.5');
  const [lArmZ, setLArmZ] = useState('3.2');
  const [h, setH] = useState('22.5');
  const [wSpan, setWSpan] = useState('23.47');
  const [saving, setSaving] = useState(false);

  async function handleSubmit() {
    if (!newId.trim() || !label.trim()) { showToast('⚠️ 请填写正式 ID 和名称'); return; }
    setSaving(true);
    try {
      await initDevice({
        temp_id: device.temp_id,
        new_vehicle_id: newId.trim(),
        label: label.trim(),
        l_arm: [parseFloat(lArmX), parseFloat(lArmY), parseFloat(lArmZ)],
        h: parseFloat(h),
        w_span: parseFloat(wSpan),
      });
      showToast(`✅ ${newId} 初始化成功，中控机将重启并以新 ID 上线`);
      onDone();
    } catch {
      showToast('❌ 初始化失败，请检查后端连接', 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-md space-y-5 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-white">初始化新设备</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-3 bg-slate-800/60 rounded-lg text-xs space-y-1 font-mono">
          <div className="flex justify-between"><span className="text-slate-500">临时 ID</span><span className="text-amber-400">{device.temp_id}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">MAC</span><span className="text-slate-300">{device.mac}</span></div>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="section-title block mb-1">正式 ID</label>
              <input className="input-field font-mono" value={newId} onChange={e => setNewId(e.target.value)} placeholder="RTG-001" />
            </div>
            <div>
              <label className="section-title block mb-1">显示名称</label>
              <input className="input-field" value={label} onChange={e => setLabel(e.target.value)} placeholder="RTG 01号机" />
            </div>
          </div>
          <div>
            <label className="section-title block mb-1">杆臂向量 L_arm [X, Y, Z] (m)</label>
            <div className="grid grid-cols-3 gap-2">
              {[['X', lArmX, setLArmX], ['Y', lArmY, setLArmY], ['Z', lArmZ, setLArmZ]].map(([axis, val, setter]) => (
                <div key={axis as string}>
                  <span className="text-[10px] text-slate-500">{axis as string}</span>
                  <input type="number" step="0.01" className="input-field font-mono text-sm py-1.5" value={val as string} onChange={e => (setter as (v: string) => void)(e.target.value)} />
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="section-title block mb-1">吊具基准高度 H (m)</label>
              <input type="number" step="0.1" className="input-field font-mono" value={h} onChange={e => setH(e.target.value)} />
            </div>
            <div>
              <label className="section-title block mb-1">跨距 W_span (m)</label>
              <input type="number" step="0.01" className="input-field font-mono" value={wSpan} onChange={e => setWSpan(e.target.value)} />
            </div>
          </div>
        </div>

        <div className="flex gap-3 pt-1">
          <button onClick={onClose} className="flex-1 btn-secondary">取消</button>
          <button onClick={handleSubmit} disabled={saving} className="flex-1 btn-primary flex items-center justify-center gap-2">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            {saving ? '初始化中…' : '确认初始化'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Settings() {
  const {
    vehicles, pendingDevices, yards,
    selectedVehicleId, setSelectedVehicleId,
    selectedYardId, setSelectedYardId,
    useMock,
    connStatus, isMock,
    backendConfig, setBackendConfig,
    switchMockMode, fetchVehicles, fetchYards,
  } = useAppContext();

  const [refreshingVehicles, setRefreshingVehicles] = useState(false);
  const [refreshingYards, setRefreshingYards] = useState(false);

  async function handleRefreshVehicles() {
    if (useMock || refreshingVehicles) return;
    setRefreshingVehicles(true);
    try { await fetchVehicles(); showToast('✅ 车辆列表已刷新'); }
    catch { showToast('⚠️ 刷新失败，请检查后端连接', 'error'); }
    finally { setRefreshingVehicles(false); }
  }

  async function handleRefreshYards() {
    if (useMock || refreshingYards) return;
    setRefreshingYards(true);
    try { await fetchYards(); showToast('✅ 场地列表已刷新'); }
    catch { showToast('⚠️ 刷新失败，请检查后端连接', 'error'); }
    finally { setRefreshingYards(false); }
  }

  const selectedVehicle = vehicles.find(v => v.vehicle_id === selectedVehicleId) ?? null;
  const selectedYard    = yards.find(y => y.yard_id === selectedYardId) ?? null;

  // 角色 C 判定：调用 GET /api/yard/map 检查 calibration_status
  const [calibrationStatus, setCalibrationStatus] = useState<'none' | 'calibrated' | null>(null);
  const [checkingRole, setCheckingRole] = useState(false);
  useEffect(() => {
    setCalibrationStatus(null);
    if (!selectedVehicleId || !selectedYardId || useMock) return;
    setCheckingRole(true);
    fetch(`http://${backendConfig.host}:${backendConfig.port}/api/yard/map?yard_id=${selectedYardId}&vehicle_id=${selectedVehicleId}`,
      { signal: AbortSignal.timeout(5000) })
      .then(r => r.ok ? r.json() : null)
      .then((json: { calibration_status?: string } | null) => {
        setCalibrationStatus((json?.calibration_status === 'calibrated') ? 'calibrated' : 'none');
      })
      .catch(() => setCalibrationStatus(null))
      .finally(() => setCheckingRole(false));
  }, [selectedVehicleId, selectedYardId, useMock, backendConfig]);

  // 角色判定（A=建图，B=校准，C=作业）
  const role: 'mapping' | 'calibration' | 'worker' | null =
    !selectedYard ? null :
    !selectedYard.mapped ? 'mapping' :
    calibrationStatus === 'calibrated' ? 'worker' :
    'calibration';

  // 待初始化设备弹窗
  const [initTarget, setInitTarget] = useState<PendingDevice | null>(null);

  // 可编辑的后端服务地址（全局统一）
  const [editingConn, setEditingConn] = useState(false);
  const [editHost, setEditHost] = useState(backendConfig.host);
  const [editPort, setEditPort] = useState(String(backendConfig.port));

  function toggleMock() {
    const next = !useMock;
    switchMockMode(next);
    showToast(next ? '🧪 已切换为模拟数据模式' : '🔌 已切换为真实连接模式，正在拉取设备列表…');
  }

  // 当后端配置变化时，重置编辑框内容
  useEffect(() => {
    setEditHost(backendConfig.host);
    setEditPort(String(backendConfig.port));
    setEditingConn(false);
  }, [backendConfig]);

  function saveConnEdit() {
    const port = parseInt(editPort, 10);
    if (!editHost.trim() || isNaN(port) || port < 1 || port > 65535) {
      showToast('⚠️ IP 或端口格式不正确');
      return;
    }
    setBackendConfig({ host: editHost.trim(), port });
    setEditingConn(false);
    showToast('✅ 后端服务地址已更新，下次连接时生效');
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* 初始化弹窗 */}
      {initTarget && (
        <InitDeviceModal
          device={initTarget}
          backendBase={`http://${backendConfig.host}:${backendConfig.port}`}
          onClose={() => setInitTarget(null)}
          onDone={() => setInitTarget(null)}
        />
      )}

      <SectionHeader
        title="工作配置"
        subtitle="选择当前操作的车辆和作业场地。场地首次建图担任「A角色」，建图后未校准的车辆担任「B角色」，已校准车辆为「C角色（作业）」。"
      />

      {/* ── 模拟数据开关 ── */}
      <div className="card p-5 border border-slate-700/60 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-slate-200">模拟数据模式</p>
          <p className="text-[10px] text-slate-500 mt-0.5">
            {useMock ? '当前使用内置仿真数据，无需中控机连接' : '当前连接真实中控机 WebSocket 数据流'}
          </p>
        </div>
        <button
          onClick={() => toggleMock()}
          className={clsx(
            'flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-bold transition-all',
            useMock
              ? 'bg-amber-900/30 border-amber-500/40 text-amber-300 hover:border-amber-400'
              : 'bg-emerald-900/30 border-emerald-500/40 text-emerald-300 hover:border-emerald-400',
          )}
        >
          {useMock ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
          {useMock ? '模拟开启' : '模拟关闭'}
        </button>
      </div>

      {/* ── 待初始化设备 ── */}
      {!useMock && pendingDevices.length > 0 && (
        <div className="card p-5 border border-amber-500/30 bg-amber-900/10 space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-bold uppercase tracking-wide text-amber-300">待初始化设备</h3>
            <span className="ml-auto text-[10px] text-amber-500">{pendingDevices.length} 台待分配</span>
          </div>
          <p className="text-[11px] text-amber-200/60">
            以下设备已上线但尚未分配正式 ID。点击「初始化」填写参数后，后端将向设备下发 CMD_INIT_IDENTITY，设备重启后以新 ID 上线。
          </p>
          <div className="space-y-2">
            {pendingDevices.map(dev => (
              <div key={dev.temp_id} className="flex items-center gap-3 p-3 bg-slate-900/60 rounded-xl border border-amber-500/20">
                <div className="w-9 h-9 rounded-lg bg-amber-900/40 border border-amber-500/30 flex items-center justify-center shrink-0">
                  <Car className="w-4 h-4 text-amber-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-amber-200 font-mono">{dev.temp_id}</p>
                  <p className="text-[10px] text-slate-500 font-mono">MAC: {dev.mac}</p>
                </div>
                <button
                  onClick={() => setInitTarget(dev)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold shrink-0"
                >
                  <Plus className="w-3.5 h-3.5" /> 初始化
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 后端服务连接面板 ── */}
      <div className="card p-5 border border-slate-700/60 space-y-4">
        <div className="flex items-center gap-2">
          {connStatus === 'connected'
            ? <Wifi className="w-4 h-4 text-emerald-400" />
            : connStatus === 'connecting'
            ? <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
            : <WifiOff className="w-4 h-4 text-slate-500" />}
          <h3 className="text-sm font-bold uppercase tracking-wide text-slate-300">后端服务连接</h3>
          <span className={clsx(
            'ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full border',
            connStatus === 'connected'
              ? 'text-emerald-400 bg-emerald-900/30 border-emerald-500/30'
              : connStatus === 'connecting'
              ? 'text-amber-400 bg-amber-900/30 border-amber-500/30'
              : 'text-slate-500 bg-slate-800 border-slate-700',
          )}>
            {connStatus === 'connected' ? '已连接' : connStatus === 'connecting' ? '连接中…' : '未连接'}
            {isMock && ' (模拟)'}
          </span>
        </div>

        <div className="space-y-3">
          <p className="text-[11px] text-slate-400">
            前端通过统一的后端服务接入，后端负责与各车辆中控机的 MQTT 通信。
            {selectedVehicleId && <span className="text-blue-400"> 当前订阅车辆：{selectedVehicleId}</span>}
          </p>

          {/* IP / 端口显示 + 编辑 */}
          {editingConn ? (
            <div className="flex items-center gap-2 flex-wrap">
              <input
                className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-slate-200 font-mono w-44 focus:outline-none focus:border-blue-500"
                value={editHost}
                onChange={e => setEditHost(e.target.value)}
                placeholder="192.168.1.200"
              />
              <span className="text-slate-500">:</span>
              <input
                className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-slate-200 font-mono w-20 focus:outline-none focus:border-blue-500"
                value={editPort}
                onChange={e => setEditPort(e.target.value)}
                placeholder="8080"
              />
              <button onClick={saveConnEdit} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold">
                <Save className="w-3.5 h-3.5" /> 保存
              </button>
              <button onClick={() => setEditingConn(false)} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs">
                <X className="w-3.5 h-3.5" /> 取消
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm text-slate-300 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-700">
                {backendConfig.host}:{backendConfig.port}
              </span>
              <button
                onClick={() => { setEditHost(backendConfig.host); setEditPort(String(backendConfig.port)); setEditingConn(true); }}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-600 hover:border-slate-400 text-slate-400 hover:text-slate-200 text-xs"
              >
                <Edit2 className="w-3.5 h-3.5" /> 修改地址
              </button>
            </div>
          )}

          <p className="text-[10px] text-slate-500">
            {useMock
              ? '模拟模式下不会发起真实连接，关闭模拟后自动连接上方地址。'
              : connStatus === 'connected'
              ? `已与后端服务 ${backendConfig.host}:${backendConfig.port} 建立 WebSocket 连接。`
              : '修改地址后，切换模拟模式或重新选择车辆以触发连接。'}
          </p>
        </div>
      </div>

      {/* ── 当前选择状态 Banner ── */}
      <div className={clsx(
        'card p-5 border',
        selectedVehicle && selectedYard
          ? role === 'mapping'
            ? 'bg-blue-900/10 border-blue-500/30'
            : 'bg-amber-900/10 border-amber-500/30'
          : 'border-slate-700/60',
      )}>
        <h3 className="section-title mb-4">当前工作配置</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 车辆 */}
          <div className="flex items-center gap-3">
            <div className={clsx(
              'w-11 h-11 rounded-xl flex items-center justify-center shrink-0',
              selectedVehicle
                ? 'bg-blue-600/20 border border-blue-500/40'
                : 'bg-slate-800 border border-slate-700',
            )}>
              <Car className={clsx('w-5 h-5', selectedVehicle ? 'text-blue-400' : 'text-slate-600')} />
            </div>
            <div>
              <p className="section-title">当前车辆</p>
              <p className={clsx('text-sm font-bold mt-0.5', selectedVehicle ? 'text-white' : 'text-slate-500')}>
                {selectedVehicle ? selectedVehicle.label : '— 未选择 —'}
              </p>
              {selectedVehicle && (
                <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                  {selectedVehicle.vehicle_id} · H={selectedVehicle.height}m · W={selectedVehicle.span}m
                </p>
              )}
            </div>
          </div>

          {/* 场地 */}
          <div className="flex items-center gap-3">
            <div className={clsx(
              'w-11 h-11 rounded-xl flex items-center justify-center shrink-0',
              selectedYard
                ? 'bg-emerald-600/20 border border-emerald-500/40'
                : 'bg-slate-800 border border-slate-700',
            )}>
              <Map className={clsx('w-5 h-5', selectedYard ? 'text-emerald-400' : 'text-slate-600')} />
            </div>
            <div>
              <p className="section-title">当前场地</p>
              <p className={clsx('text-sm font-bold mt-0.5', selectedYard ? 'text-white' : 'text-slate-500')}>
                {selectedYard ? selectedYard.name : '— 未选择 —'}
              </p>
              {selectedYard && (
                <p className={clsx('text-[10px] font-bold mt-0.5', selectedYard.mapped ? 'text-emerald-400' : 'text-amber-400')}>
                  {selectedYard.mapped ? '● 已建图' : '○ 未建图'} · {selectedYard.total_bays} 贝位
                </p>
              )}
            </div>
          </div>
        </div>

        {/* 角色提示 */}
        {selectedVehicle && selectedYard && (
          <div className={clsx(
            'mt-4 p-3 rounded-lg text-xs flex items-start gap-2 border',
            role === 'mapping'
              ? 'bg-blue-900/20 border-blue-500/20 text-blue-300'
              : role === 'worker'
              ? 'bg-emerald-900/20 border-emerald-500/20 text-emerald-300'
              : 'bg-amber-900/20 border-amber-500/20 text-amber-300',
          )}>
            {checkingRole ? (
              <><Loader2 className="w-4 h-4 shrink-0 animate-spin" /><span>正在查询校准状态…</span></>
            ) : role === 'mapping' ? (
              <>
                <Map className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  <span className="font-bold">角色 A · 建图</span> — {selectedYard.name} 尚无底图，
                  {selectedVehicle.label} 将前往「场地建图」页面采集贝位坐标。
                </span>
              </>
            ) : role === 'worker' ? (
              <>
                <Zap className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  <span className="font-bold">角色 C · 作业</span> — {selectedVehicle.label} 在 {selectedYard.name} 已完成校准，
                  直接进入高频定位作业模式，前往「仪表盘」查看实时数据。
                </span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  <span className="font-bold">角色 B · 校准</span> — {selectedYard.name} 已有底图，
                  {selectedVehicle.label} 将前往「车辆校准」页面完成 3 点标定，生成本车转换矩阵。
                </span>
              </>
            )}
          </div>
        )}

        {(!selectedVehicle || !selectedYard) && (
          <div className="mt-4 p-3 rounded-lg text-xs flex items-center gap-2 bg-slate-900/60 border border-slate-700/40 text-slate-400">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            请在下方分别选择车辆和场地，以确定当前工作配置。
          </div>
        )}
      </div>

      {/* ── 两栏选择面板 ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* 左栏：车辆列表 */}
        <div className="card p-6 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-700/60">
            <Car className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-300">车辆列表</h3>
            <span className="text-[10px] text-slate-500">{vehicles.length} 台注册</span>
            <button
              onClick={handleRefreshVehicles}
              disabled={useMock || refreshingVehicles}
              title={useMock ? '模拟模式下不可刷新' : '从后端重新拉取车辆列表'}
              className="ml-auto p-1.5 rounded-lg text-slate-500 hover:text-blue-400 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <RefreshCw className={clsx('w-3.5 h-3.5', refreshingVehicles && 'animate-spin')} />
            </button>
          </div>

          <div className="space-y-2">
            {vehicles.map((v) => {
              const isSelected = v.vehicle_id === selectedVehicleId;
              return (
                <button
                  key={v.vehicle_id}
                  onClick={() => {
                    setSelectedVehicleId(isSelected ? null : v.vehicle_id);
                    if (!isSelected) showToast(`✅ 已选择：${v.label}`);
                  }}
                  className={clsx(
                    'w-full text-left p-4 rounded-xl border transition-all duration-150',
                    isSelected
                      ? 'bg-blue-900/30 border-blue-500/60 shadow-lg shadow-blue-900/20'
                      : 'bg-slate-900/40 border-slate-700/60 hover:border-slate-500',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className={clsx(
                      'w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold shrink-0',
                      isSelected ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400',
                    )}>
                      {v.vehicle_id.slice(-3)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={clsx('text-sm font-bold truncate', isSelected ? 'text-blue-200' : 'text-slate-200')}>
                        {v.label}
                      </p>
                      <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                        {v.vehicle_id} · {v.antennas.length} 天线 · H={v.height}m · W={v.span}m
                      </p>
                    </div>
                    {isSelected && <CheckCircle2 className="w-5 h-5 text-blue-400 shrink-0" />}
                  </div>
                </button>
              );
            })}
          </div>

          <p className="text-[10px] text-slate-600 text-center pt-1">
            天线杆臂等几何参数请在「参数配置」页编辑
          </p>
        </div>

        {/* 右栏：场地列表 */}
        <div className="card p-6 space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-700/60">
            <Map className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-300">场地列表</h3>
            <span className="text-[10px] text-slate-500">
              {yards.filter(y => y.mapped).length}/{yards.length} 已建图
            </span>
            <button
              onClick={handleRefreshYards}
              disabled={useMock || refreshingYards}
              title={useMock ? '模拟模式下不可刷新' : '从后端重新拉取场地列表'}
              className="ml-auto p-1.5 rounded-lg text-slate-500 hover:text-emerald-400 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <RefreshCw className={clsx('w-3.5 h-3.5', refreshingYards && 'animate-spin')} />
            </button>
          </div>

          <div className="space-y-2">
            {yards.map((y) => {
              const isSelected = y.yard_id === selectedYardId;
              return (
                <button
                  key={y.yard_id}
                  onClick={() => {
                    setSelectedYardId(isSelected ? null : y.yard_id);
                    if (!isSelected) showToast(`✅ 已选择：${y.name}`);
                  }}
                  className={clsx(
                    'w-full text-left p-4 rounded-xl border transition-all duration-150',
                    isSelected
                      ? 'bg-emerald-900/30 border-emerald-500/60 shadow-lg shadow-emerald-900/20'
                      : 'bg-slate-900/40 border-slate-700/60 hover:border-slate-500',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className={clsx(
                      'w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold shrink-0',
                      isSelected ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400',
                    )}>
                      {y.yard_id.slice(-2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={clsx('text-sm font-bold truncate', isSelected ? 'text-emerald-200' : 'text-slate-200')}>
                        {y.name}
                      </p>
                      <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                        {y.yard_id} · {y.total_bays} 贝位 · 朝向 {y.heading}°
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={clsx(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full border',
                        y.mapped
                          ? 'text-emerald-400 bg-emerald-900/30 border-emerald-500/30'
                          : 'text-amber-400 bg-amber-900/30 border-amber-500/30',
                      )}>
                        {y.mapped ? '已建图' : '未建图'}
                      </span>
                      {isSelected && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* 说明框 */}
          <div className="p-3 bg-slate-900/60 border border-slate-700/40 rounded-lg">
            <p className="text-[10px] text-slate-500 leading-relaxed">
              💡 <span className="text-slate-400 font-semibold">角色说明：</span>
              同一台车，在「未建图」场地为建图角色；在「已建图」场地为校准角色。
              角色由场地状态决定，与车辆编号无关。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
