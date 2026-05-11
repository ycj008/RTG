# RTG 系统启动脚本
Write-Host "RTG 高精度自动定位系统" -ForegroundColor Green
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\Activate.ps1"
pip install -q -r requirements.txt
python src\main.py
