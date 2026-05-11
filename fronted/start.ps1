# RTG 前端启动脚本
# 用法：在 fronted/ 目录下运行 .\start.ps1
# 或在项目根目录运行 .\fronted\start.ps1

$ErrorActionPreference = "Stop"

$frontedDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $frontedDir

Write-Host "=== RTG 前端启动 ===" -ForegroundColor Cyan

# 检查 Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 未找到 Node.js，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

$nodeVer = node --version
Write-Host "Node.js 版本: $nodeVer" -ForegroundColor Gray

# 检查并安装依赖
if (-not (Test-Path "node_modules")) {
    Write-Host "[提示] 未找到 node_modules，正在安装依赖..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 依赖安装失败" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "启动开发服务器..." -ForegroundColor Green
Write-Host "访问地址: http://localhost:5173" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Gray
Write-Host ""

npm run dev
