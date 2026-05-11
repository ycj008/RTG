/**
 * 前端统一日志工具
 * - 开发模式下：输出到浏览器 Console，同时异步 POST 到 Vite 中间件，在终端也能看到
 * - 生产模式下：只输出 info / warn / error，屏蔽 debug
 * 使用：logger.info('WebSocket', '已连接', { url })
 */

/// <reference types="vite/client" />

const isDev = import.meta.env.DEV;

type Level = 'info' | 'warn' | 'error' | 'debug';

const STYLES: Record<Level, string> = {
  info:  'color:#60a5fa;font-weight:bold',
  warn:  'color:#fbbf24;font-weight:bold',
  error: 'color:#f87171;font-weight:bold',
  debug: 'color:#a78bfa;font-weight:bold',
};

function sendToTerminal(level: Level, module: string, time: string, msg: string, args: unknown[]) {
  fetch('/__dev_log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level, module, time, msg, args }),
  }).catch(() => { /* 终端转发失败时静默 */ });
}

// StrictMode 下同一条日志会连续触发两次，500ms 内去重
const recentLogs = new Map<string, number>();
function isDuplicate(key: string): boolean {
  const now = Date.now();
  const last = recentLogs.get(key);
  if (last && now - last < 100) return true;
  recentLogs.set(key, now);
  if (recentLogs.size > 500) {
    const oldest = [...recentLogs.entries()].sort((a, b) => a[1] - b[1])[0][0];
    recentLogs.delete(oldest);
  }
  return false;
}

function log(level: Level, module: string, msg: string, ...args: unknown[]) {
  if (!isDev && level === 'debug') return;
  if (isDev && isDuplicate(`${level}|${module}|${msg}`)) return;
  const d = new Date();
  const time = d.toLocaleTimeString('zh-CN', { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0');
  const fn = level === 'error' ? console.error
           : level === 'warn'  ? console.warn
           : console.log;
  fn(`%c${time}%c %c[${module}]%c ${msg}`, 'color:#64748b', '', STYLES[level], '', ...args);
  if (isDev) sendToTerminal(level, module, time, msg, args);
}

export const logger = {
  info:  (module: string, msg: string, ...args: unknown[]) => log('info',  module, msg, ...args),
  warn:  (module: string, msg: string, ...args: unknown[]) => log('warn',  module, msg, ...args),
  error: (module: string, msg: string, ...args: unknown[]) => log('error', module, msg, ...args),
  debug: (module: string, msg: string, ...args: unknown[]) => log('debug', module, msg, ...args),
};
