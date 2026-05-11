import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'

// ── 终端日志中间件插件 ──────────────────────────────────
// 浏览器端 logger 将日志 POST 到 /__dev_log，此插件在终端打印
const COLORS: Record<string, string> = {
  info:  '\x1b[34m',   // 蓝
  warn:  '\x1b[33m',   // 黄
  error: '\x1b[31m',   // 红
  debug: '\x1b[35m',   // 紫
};
const RESET = '\x1b[0m';
const BOLD  = '\x1b[1m';

function terminalLogPlugin(): Plugin {
  return {
    name: 'terminal-log',
    configureServer(server) {
      server.middlewares.use('/__dev_log', (req, res) => {
        if (req.method !== 'POST') { res.end(); return; }
        let body = '';
        req.on('data', (chunk: Buffer) => { body += chunk.toString(); });
        req.on('end', () => {
          try {
            const { level, module, time, msg, args } = JSON.parse(body) as {
              level: string; module: string; time: string; msg: string; args: unknown[];
            };
            const color = COLORS[level] ?? RESET;
            const extra = args.length ? ' ' + args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ') : '';
            console.log(`\x1b[90m${time}\x1b[0m ${color}${BOLD}[${module}]${RESET} ${msg}${extra}`);
          } catch { /* ignore */ }
          res.statusCode = 204;
          res.end();
        });
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), terminalLogPlugin()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
