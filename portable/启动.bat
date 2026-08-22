@echo off
title Get Jobs Auto
cd /d "%~dp0"

echo ========================================
echo   Get Jobs Auto 启动中...
echo ========================================
echo.

:: 1. 查找 Chrome 浏览器
echo [1/5] 检测 Chrome 浏览器...
set "CHROME_PATH="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%USERPROFILE%\AppData\Local\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%USERPROFILE%\AppData\Local\Google\Chrome\Application\chrome.exe"

if not defined CHROME_PATH (
    echo [错误] 未检测到 Chrome 浏览器！
    echo 请先安装 Chrome: https://www.google.com/chrome/
    echo.
    pause
    exit /b 1
)
echo       找到 Chrome: %CHROME_PATH%

:: 2. 检测 8888 端口
echo [2/5] 检测端口状态...
netstat -ano | findstr ":8888 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 8888 端口已被占用，服务可能已在运行
    start http://127.0.0.1:8888
    echo.
    echo 如果页面无法访问，请运行 停止.bat 后重新启动
    pause
    exit /b 0
)
echo       端口空闲

:: 3. 启动 Chrome 调试模式
echo [3/5] 启动 Chrome 调试模式...
if not exist "user-data\chrome-data" mkdir "user-data\chrome-data"
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%~dp0user-data\chrome-data" about:blank
echo       Chrome 已启动（端口 9222）

:: 4. 等待 Chrome 启动
timeout /t 3 /nobreak >nul

:: 5. 启动后端服务
echo [4/5] 启动后端服务...
echo.
echo ========================================
echo   Get Jobs Auto 已启动
echo   管理页面: http://127.0.0.1:8888
echo   API文档:  http://127.0.0.1:8888/docs
echo.
echo   关闭此窗口将停止服务
echo ========================================
echo.

:: 延迟2秒后自动打开浏览器
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8888"

:: 用便携版 Python 启动后端
"runtime\python.exe" "..\backend\run.py"

pause

