@echo off
chcp 65001 >nul
title 阿尔法智投 - AI 智能投资顾问系统

echo ============================================
echo   阿尔法智投 AI 智能投资顾问系统
echo   2026 秋 AI+工程管理课程项目
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] 检查 Python 环境...
python --version
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo [2/3] 检查依赖包...
python -c "import streamlit, akshare, scipy, openai, plotly, dotenv" 2>nul
if errorlevel 1 (
    echo 依赖缺失，正在安装...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
)
echo 依赖检查通过

echo [3/3] 启动 Streamlit 服务...
echo.
echo 应用将在浏览器中自动打开: http://localhost:8501
echo 按 Ctrl+C 可停止服务
echo.
streamlit run app.py --server.port 8501
pause
