# RTG 中控机程序启动脚本
# 使用方法：.\run_controller.ps1

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  RTG 高精度定位系统 - 中控机程序" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# 检查虚拟环境
if (-not (Test-Path ".venv")) {
    Write-Host "⚠ 未检测到虚拟环境，正在创建..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✓ 虚拟环境创建完成" -ForegroundColor Green
}

# 激活虚拟环境
Write-Host "正在激活虚拟环境..." -ForegroundColor Gray
& .\.venv\Scripts\Activate.ps1

# 检查依赖
Write-Host "检查依赖包..." -ForegroundColor Gray
$missingPackages = @()

try {
    python -c "import numpy" 2>$null
} catch {
    $missingPackages += "numpy"
}

try {
    python -c "import paho.mqtt" 2>$null
} catch {
    $missingPackages += "paho-mqtt"
}

try {
    python -c "import requests" 2>$null
} catch {
    $missingPackages += "requests"
}

if ($missingPackages.Count -gt 0) {
    Write-Host "⚠ 缺少依赖包，正在安装..." -ForegroundColor Yellow
    pip install -r requirements.txt
    Write-Host "✓ 依赖包安装完成" -ForegroundColor Green
}

# 创建必要的目录
Write-Host "检查目录结构..." -ForegroundColor Gray
$directories = @("logs", "data")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "✓ 创建目录: $dir" -ForegroundColor Green
    }
}

# 启动程序
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  正在启动中控机程序..." -ForegroundColor Cyan
Write-Host "  按 Ctrl+C 停止程序" -ForegroundColor Yellow
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

python -m src.main

