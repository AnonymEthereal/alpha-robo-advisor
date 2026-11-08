# 阿尔法智投 启动脚本 (PowerShell)
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  阿尔法智投 AI 智能投资顾问系统" -ForegroundColor Cyan
Write-Host "  2026 秋 AI+工程管理课程项目" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

Write-Host "[1/3] 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pyVer = python --version 2>&1
    Write-Host "  $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  [错误] 未找到 Python，请先安装 Python 3.10+" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

Write-Host "[2/3] 检查依赖包..." -ForegroundColor Yellow
$check = python -c "import streamlit, akshare, scipy, openai, plotly, dotenv; print('ok')" 2>&1
if ($check -ne "ok") {
    Write-Host "  依赖缺失，正在安装..." -ForegroundColor Yellow
    pip install -r requirements.txt --no-build-isolation
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [错误] 依赖安装失败" -ForegroundColor Red
        Read-Host "按回车退出"
        exit 1
    }
}
Write-Host "  依赖检查通过" -ForegroundColor Green

Write-Host "[3/3] 启动 Streamlit 服务..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  应用将在浏览器中自动打开: http://localhost:8501" -ForegroundColor Cyan
Write-Host "  按 Ctrl+C 可停止服务" -ForegroundColor Gray
Write-Host ""
streamlit run app.py --server.port 8501
