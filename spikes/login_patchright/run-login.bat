@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Get Jobs Auto - Boss Login
cd /d "%~dp0..\..\"
echo Opening Boss QR login browser, please scan in the popup window...
py -3.12 "spikes\login_patchright\spike.py" wait-login --timeout 300
echo.
echo Finished. Press any key to close this window.
pause >nul
