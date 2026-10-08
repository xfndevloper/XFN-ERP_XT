@echo off
title XFN-ERP_NEXT Mobile Cloud Link - Xfinity Buildcon
cd /d "C:\XFN-ERP_NEXT"
echo ============================================================
echo   LAUNCHING FREE CLOUD TUNNEL FOR 150+ MOBILE WORKERS
echo   (No Port Forwarding, No Credit Card, 100%% Free)
echo ============================================================
echo.
cloudflared.exe tunnel --url http://localhost:8000
pause
