@echo off
cd /d g:\sxxm\backend
echo ========================================
echo  正在释放端口8001...
echo ========================================
python -c "import socket;s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('0.0.0.0',8001));s.listen();print('Port 8001 released');s.close()"
echo.
echo ========================================
echo  正在启动后端服务（端口8001，无热重载）
echo ========================================
python restart_backend.py
echo.
echo 服务已停止，按任意键退出...
pause >nul
