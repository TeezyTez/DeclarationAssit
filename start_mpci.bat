@echo off
REM MPCI Q&A System - Quick Start
cd /d "d:\Users\Desktop\EDI\ARE\MPCI"

if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
) else (
    set MPCI_LLM_TYPE=auto
    set MPCI_HOST=0.0.0.0
    set MPCI_PORT=8000
)

echo ========================================
echo   MPCI 智能问答系统
echo ========================================
echo   启动中，请稍候...
echo   访问地址：http://localhost:8000
echo   LLM模式：%MPCI_LLM_TYPE%
echo   按 Ctrl+C 停止服务
echo ========================================

python -m mpci_qa.app

pause
