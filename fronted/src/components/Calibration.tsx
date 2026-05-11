import { useState } from 'react';
import { Zap, CheckCircle2, Circle, ArrowRight, AlertTriangle, Map } from 'lucide-react';
import { SectionHeader, showToast, InfoRow } from './common';
import { useAppContext } from '../context/AppContext';
import type { CalibrationStep, RealtimeData } from '../types';
import { clsx } from 'clsx';
import { logger } from '../utils/logger';interface CalibrationProps {
  liveData: RealtimeData;
}

const STEP_BAYS = ['Bay_01', 'Bay_04', 'Bay_08'];
const STEP_DESCS = [
  '将 B 车左门腿中心线对准 Bay_01，系统将采集当前坐标与底图对比，求解平移偏差 (ΔX, ΔY)。',
  '移动至 Bay_04，系统将利用两点求解旋转偏差 Δθ。',
  '移动至 Bay_08，用于冗余校验与尺度纠偏，锁定最终转换矩阵 M。',
];

const initSteps = (): CalibrationStep[] => [
  { step: 1, bay_id: 'Bay_01', status: 'waiting' },
  { step: 2, bay_id: 'Bay_04', status: 'waiting' },
  { step: 3, bay_id: 'Bay_08', status: 'waiting' },
];

export default function Calibration({ liveData }: CalibrationProps) {
  const { vehicles, yards, selectedVehicleId, selectedYardId, backendConfig } = useAppContext();
  const selectedVehicle = vehicles.find(v => v.vehicle_id === selectedVehicleId) ?? null;
  const selectedYard    = yards.find(y => y.yard_id === selectedYardId) ?? null;

  const [steps, setSteps] = useState<CalibrationStep[]>(initSteps());
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState(false);

  const baseUrl = `http://${backendConfig.host}:${backendConfig.port}`;
  const isInRange = true; // simulated: always in range

  const handleConfirm = async () => {
    if (confirming) return;
    setConfirming(true);

    // 等待中控机采样（实际由后端 MQTT 驱动）
    await new Promise((r) => setTimeout(r, 1500));

    const measured = {
      x: liveData.local_coord.x + (Math.random() - 0.5) * 0.1,
      y: liveData.local_coord.y + (Math.random() - 0.5) * 0.1,
      z: liveData.local_coord.z,
    };
    const reference = {
      x: measured.x + (Math.random() - 0.5) * 0.05,
      y: measured.y + (Math.random() - 0.5) * 0.05,
      z: measured.z,
    };
    const delta = {
      x: parseFloat((measured.x - reference.x).toFixed(4)),
      y: parseFloat((measured.y - reference.y).toFixed(4)),
      z: parseFloat((measured.z - reference.z).toFixed(4)),
    };

    setSteps((prev) =>
      prev.map((s) =>
        s.step === currentStep
          ? { ...s, status: 'done', measured, reference, delta }
          : s,
      ),
    );

    if (currentStep < 3) {
      // §3.1 每步打点：POST /api/survey/confirm (mode: "B")
      const confirmPayload = {
        vehicle_id: selectedVehicleId,
        yard_id: selectedYard?.yard_id,
        bay_id: STEP_BAYS[currentStep - 1],
        mode: 'B',
      };
      logger.info('Calibration', `POST /api/survey/confirm 步骤${currentStep}`, confirmPayload);
      try {
        const res = await fetch(`${baseUrl}/api/survey/confirm`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(confirmPayload),
        });
        if (res.ok) {
          logger.info('Calibration', `步骤${currentStep} confirm 成功`);
        } else {
          logger.warn('Calibration', `步骤${currentStep} confirm HTTP ${res.status}`);
        }
      } catch (e) { logger.error('Calibration', 'confirm 请求失败', e); }
      setCurrentStep((prev) => (prev + 1) as 1 | 2 | 3);
      showToast(`✅ 第 ${currentStep} 点校准完成，ΔX=${delta.x}m, ΔY=${delta.y}m`);
    } else {
      // §3.2 最终步：POST /api/survey/finalize
      const finalPayload = { vehicle_id: selectedVehicleId, yard_id: selectedYard?.yard_id, steps };
      logger.info('Calibration', 'POST /api/survey/finalize', { vehicle_id: finalPayload.vehicle_id, yard_id: finalPayload.yard_id, steps_count: steps.length });
      try {
        const res = await fetch(`${baseUrl}/api/survey/finalize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(finalPayload),
        });
        if (res.ok) {
          logger.info('Calibration', '校准 finalize 成功');
        } else {
          logger.warn('Calibration', `finalize HTTP ${res.status}`);
        }
      } catch (e) { logger.error('Calibration', 'finalize 请求失败', e); }
      setDone(true);
      showToast('🎉 车辆校准完成！转换矩阵 M 已写入数据库');
    }

    setConfirming(false);
  };

  const handleReset = () => {
    setSteps(initSteps());
    setCurrentStep(1);
    setDone(false);
  };

  // ── 未选择车辆 ──
  if (!selectedVehicle) {
    return (
      <div className="animate-fade-in flex items-center justify-center min-h-[60vh]">
        <div className="card p-12 max-w-md w-full text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto" />
          <h2 className="text-xl font-bold text-white">未选择车辆</h2>
          <p className="text-slate-400 text-sm">请前往「工作配置」页面选择当前操作的车辆。</p>
        </div>
      </div>
    );
  }

  // ── 未选择场地 ──
  if (!selectedYard) {
    return (
      <div className="animate-fade-in flex items-center justify-center min-h-[60vh]">
        <div className="card p-12 max-w-md w-full text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto" />
          <h2 className="text-xl font-bold text-white">未选择作业场地</h2>
          <p className="text-slate-400 text-sm">请前往「工作配置」页面选择当前场地。</p>
        </div>
      </div>
    );
  }

  // ── 场地尚未建图 ──
  if (!selectedYard.mapped) {
    return (
      <div className="animate-fade-in flex items-center justify-center min-h-[60vh]">
        <div className="card p-12 max-w-md w-full text-center space-y-4">
          <Map className="w-12 h-12 text-blue-400 mx-auto" />
          <h2 className="text-xl font-bold text-white">{selectedYard.name} 尚未建图</h2>
          <p className="text-slate-400 text-sm">
            该场地还没有底图数据，无法执行车辆校准。
            请先前往「场地建图」页面完成建图后再回来。
          </p>
        </div>
      </div>
    );
  }

  // ── 校准完成 ──
  if (done) {
    return (
      <div className="animate-fade-in flex items-center justify-center min-h-[60vh]">
        <div className="card p-12 max-w-lg w-full text-center space-y-6">
          <div className="w-20 h-20 bg-emerald-500/10 border border-emerald-500/30 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-10 h-10 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">车辆校准完成</h2>
            <p className="text-slate-400 text-sm mt-2">
              {selectedVehicle.label} 在 {selectedYard.name} 的转换矩阵 M 已保存，后续将使用底图进行精确定位。
            </p>
          </div>

          <div className="bg-slate-900/60 rounded-xl p-4 text-left space-y-2 border border-slate-700/60">
            {steps.map((s) => s.delta && (
              <div key={s.step} className="text-xs font-mono">
                <span className="text-slate-500">点 {s.step} ({s.bay_id})</span>
                <span className="ml-3 text-emerald-400">
                  ΔX={s.delta.x}m, ΔY={s.delta.y}m, ΔZ={s.delta.z}m
                </span>
              </div>
            ))}
          </div>

          <button onClick={handleReset} className="btn-secondary w-full">
            重新校准
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in space-y-6">
      <SectionHeader
        title={`车辆校准 · ${selectedVehicle.label}`}
        subtitle={`在「${selectedYard.name}」底图上执行 3 点标定，消除安装误差，生成本车转换矩阵 M。`}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Step wizard */}
        <div className="lg:col-span-2 space-y-4">
          {/* Progress bar */}
          <div className="card p-5">
            <div className="flex items-center gap-0 mb-6">
              {steps.map((s, i) => (
                <div key={s.step} className="flex items-center flex-1">
                  <div className={clsx(
                    'w-10 h-10 rounded-full border-2 flex items-center justify-center font-bold text-sm transition-all',
                    s.status === 'done'
                      ? 'bg-emerald-600 border-emerald-500 text-white'
                      : s.step === currentStep
                      ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-900/40'
                      : 'bg-slate-800 border-slate-600 text-slate-500',
                  )}>
                    {s.status === 'done' ? <CheckCircle2 className="w-5 h-5" /> : s.step}
                  </div>
                  {i < steps.length - 1 && (
                    <div className={clsx(
                      'flex-1 h-0.5 mx-1',
                      s.status === 'done' ? 'bg-emerald-500' : 'bg-slate-700',
                    )} />
                  )}
                </div>
              ))}
            </div>

            {/* Current step info */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="section-title">第 {currentStep} 步 / 共 3 步</span>
                {currentStep === 3 && (
                  <span className="badge bg-amber-900/30 text-amber-400 border-amber-500/30">最后一步</span>
                )}
              </div>
              <h3 className="text-lg font-bold text-white">
                驾驶至 {STEP_BAYS[currentStep - 1]}
              </h3>
              <p className="text-sm text-slate-400 leading-relaxed">
                {STEP_DESCS[currentStep - 1]}
              </p>
            </div>
          </div>

          {/* Live position */}
          <div className="card p-5 space-y-3">
            <p className="section-title">当前位置（实时）</p>
            <InfoRow label="X (LYCS)" value={`${liveData.local_coord.x.toFixed(4)} m`} />
            <InfoRow label="Y (LYCS)" value={`${liveData.local_coord.y.toFixed(4)} m`} />
            <InfoRow label="Heading"  value={`${liveData.heading.toFixed(2)}°`} />
            <InfoRow label="GNSS 状态" value={
              <span className={liveData.status === 'fix' ? 'text-emerald-400 font-bold' : 'text-amber-400'}>
                {liveData.status === 'fix' ? 'RTK FIXED' : 'FLOAT'}
              </span>
            } mono={false} />
          </div>

          {/* Confirm button */}
          <div className="card p-5 space-y-3">
            <div className={clsx(
              'flex items-center gap-2 p-3 rounded-lg text-sm',
              isInRange
                ? 'bg-emerald-900/20 border border-emerald-500/30 text-emerald-400'
                : 'bg-amber-900/20 border border-amber-500/30 text-amber-400',
            )}>
              {isInRange ? (
                <><CheckCircle2 className="w-4 h-4" /> 车辆已在目标位置附近 (≤ 0.5m)</>
              ) : (
                <><AlertTriangle className="w-4 h-4" /> 请驾驶至目标贝位附近</>
              )}
            </div>

            <button
              onClick={handleConfirm}
              disabled={confirming || !isInRange || liveData.status === 'no_signal'}
              className="w-full py-4 rounded-xl font-bold text-base transition-all duration-150 shadow-lg flex items-center justify-center gap-2
                bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white shadow-blue-900/30
                disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {confirming ? (
                <>采集中...</>
              ) : currentStep < 3 ? (
                <>确认位置，进入第 {currentStep + 1} 步 <ArrowRight className="w-5 h-5" /></>
              ) : (
                <>完成校准，生成矩阵 M <Zap className="w-5 h-5" /></>
              )}
            </button>
          </div>
        </div>

        {/* Results panel */}
        <div className="lg:col-span-3 card p-6">
          <p className="section-title mb-5">各点校准结果</p>
          <div className="space-y-4">
            {steps.map((s) => (
              <div
                key={s.step}
                className={clsx(
                  'rounded-xl border p-5 transition-all',
                  s.status === 'done'
                    ? 'bg-emerald-900/10 border-emerald-500/30'
                    : s.step === currentStep
                    ? 'bg-blue-900/10 border-blue-500/30'
                    : 'bg-slate-900/40 border-slate-700/40',
                )}
              >
                <div className="flex items-center gap-3 mb-4">
                  {s.status === 'done' ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : s.step === currentStep ? (
                    <div className="w-5 h-5 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
                  ) : (
                    <Circle className="w-5 h-5 text-slate-600" />
                  )}
                  <span className="font-bold text-white">
                    第 {s.step} 点 — {s.bay_id}
                  </span>
                  {s.status === 'done' && (
                    <span className="ml-auto badge badge-fix">已完成</span>
                  )}
                  {s.step === currentStep && s.status !== 'done' && (
                    <span className="ml-auto badge bg-blue-900/30 text-blue-400 border-blue-500/30">进行中</span>
                  )}
                </div>

                {s.status === 'done' && s.delta && s.measured && s.reference ? (
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <p className="section-title mb-2">测量坐标（当前车辆）</p>
                      <p className="font-mono text-xs text-slate-300">X: {s.measured.x.toFixed(4)}</p>
                      <p className="font-mono text-xs text-slate-300">Y: {s.measured.y.toFixed(4)}</p>
                    </div>
                    <div>
                      <p className="section-title mb-2">参考坐标 (底图)</p>
                      <p className="font-mono text-xs text-slate-300">X: {s.reference.x.toFixed(4)}</p>
                      <p className="font-mono text-xs text-slate-300">Y: {s.reference.y.toFixed(4)}</p>
                    </div>
                    <div>
                      <p className="section-title mb-2">偏差 (Δ)</p>
                      <p className={clsx('font-mono text-xs font-bold', Math.abs(s.delta.x) < 0.05 ? 'text-emerald-400' : 'text-amber-400')}>
                        ΔX: {s.delta.x >= 0 ? '+' : ''}{s.delta.x}
                      </p>
                      <p className={clsx('font-mono text-xs font-bold', Math.abs(s.delta.y) < 0.05 ? 'text-emerald-400' : 'text-amber-400')}>
                        ΔY: {s.delta.y >= 0 ? '+' : ''}{s.delta.y}
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-500">
                    {s.step === currentStep ? '等待确认操作...' : '等待前序步骤完成'}
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Formula hint */}
          <div className="mt-6 p-4 bg-slate-900/60 rounded-xl border border-slate-700/40">
            <p className="section-title mb-2">最终输出公式</p>
            <p className="font-mono text-xs text-slate-400">
              P_final_output = M × P_final
              <br />
              <span className="text-slate-600">其中 M 由 3 点 SVD 最小二乘求解</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
