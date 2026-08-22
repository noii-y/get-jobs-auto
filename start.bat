@echo off
chcp 65001 >nul
title Get Jobs Auto
cd /d "%~dp0"

echo ========================================
echo   Get Jobs Auto 启动中...
echo ========================================
echo.

:: 1. 检测 Python 3.12
set "PYTHON_CMD="
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3.12 --version >nul 2>&1
    if %errorlevel% equ 0 set "PYTHON_CMD=py -3.12"
)
if not defined PYTHON_CMD (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PYVER=%%i"
        echo %PYVER% | findstr /b "3.12" >nul
        if %errorlevel% equ 0 set "PYTHON_CMD=python"
    )
)
if not defined PYTHON_CMD (
    echo [错误] 未找到 Python 3.12，请安装 Python 3.12
    echo   下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [1/3] Python: %PYTHON_CMD%

:: 2. 检测依赖
%PYTHON_CMD% -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo [2/3] 安装依赖...
    %PYTHON_CMD% -m pip install -r backend\requirements.txt
) else (
    echo [2/3] 依赖已安装
)

:: 3. 检测 Chrome
echo [3/3] 检测浏览器...
set "CHROME_PATH="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if defined CHROME_PATH (
    echo       找到: %CHROME_PATH%
) else (
    echo [警告] 未找到 Chrome/Edge，请先安装
    echo   下载地址: https://www.google.com/chrome/
)

echo.
echo ========================================
echo   Get Jobs Auto 已启动
echo   管理页面: http://127.0.0.1:8888
echo   API文档:  http://127.0.0.1:8888/docs
echo.
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

:: 2秒后自动打开浏览器
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8888"

cd backend
%PYTHON_CMD% run.py

pause
