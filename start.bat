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

:: 2. 环境自检 doctor（缺依赖时自动安装后重跑）
echo [2/3] 环境自检 doctor...
cd /d "%~dp0backend"
%PYTHON_CMD% doctor.py
if errorlevel 1 goto doctor_fix
goto doctor_done

:doctor_fix
%PYTHON_CMD% -c "import fastapi" >nul 2>&1
if not errorlevel 1 goto doctor_fail
echo      检测到依赖缺失，正在自动安装...
%PYTHON_CMD% -m pip install -r requirements.txt
%PYTHON_CMD% doctor.py
if errorlevel 1 goto doctor_fail
goto doctor_done

:doctor_fail
echo.
echo [错误] 环境自检未通过，请根据上面报告修复后再启动。
pause
exit /b 1

:doctor_done
cd /d "%~dp0"

:: 3. 启动服务（run.py 会自动识别"本软件已在运行"并打开页面，不会重复绑定端口）
echo [3/3] 启动服务...
echo.
echo ========================================
echo   Get Jobs Auto
echo   管理页面: http://127.0.0.1:8888
echo   API文档:  http://127.0.0.1:8888/docs
echo.
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8888"

cd backend
%PYTHON_CMD% run.py

pause
