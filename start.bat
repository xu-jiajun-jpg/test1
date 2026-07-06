@echo off
chcp 65001 >nul
title 物流分拣平台 - 启动

echo ========================================
echo   📦 物流分拣平台 v1.0
echo ========================================

cd /d "%~dp0"
start "后端-8003" cmd /c "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload"
timeout /t 3 /nobreak >nul
start "前端-8080" cmd /c "cd frontend && npm run serve"
start "小程序-8081" cmd /c "cd miniapp-standalone && python -m http.server 8081"

echo.
echo   管理端:  http://localhost:8080
echo   小程序:  http://localhost:8081
echo   API文档: http://localhost:8003/docs
echo   默认账号: admin / admin123
echo.
pause
