@echo off
title Get Jobs Auto - 停止服务
cd /d "%~dp0"

echo ========================================
echo   正在停止 Get Jobs Auto...
echo ========================================
echo.

:: 停止后端服务（8888端口）
echo [1/2] 停止后端服务...
set "FOUND=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8888 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo       已停止进程 %%a
    set "FOUND=1"
)
if "%FOUND%"=="0" echo       后端服务未运行

:: 停止 Chrome 调试模式（9222端口）
echo [2/2] 停止 Chrome 调试模式...
set "FOUND=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":9222 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo       已停止 Chrome 进程 %%a
    set "FOUND=1"
)
if "%FOUND%"=="0" echo       Chrome 调试模式未运行

echo.
echo ========================================
echo   服务已停止
echo ========================================
timeout /t 3 /nobreak >nul
