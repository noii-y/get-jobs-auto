@echo off
chcp 65001 >nul
title Get Jobs Auto
cd /d "%~dp0"

echo ========================================
echo   Get Jobs Auto 启动中...
echo ========================================
echo.

:: 1. 检查本软件是否已在运行（对齐 doctor：探测 /api/health）
echo [1/4] 检查服务状态...
"runtime\python.exe" "..\backend\doctor.py" --is-running
if errorlevel 1 goto port_not_ours
echo [提示] 本软件已在运行，直接打开页面。
start http://127.0.0.1:8888
echo.
echo 如页面无法打开，请先运行 停止.bat 后重试。
pause
exit /b 0

:port_not_ours
netstat -ano | findstr ":8888 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo       端口空闲
) else (
    echo [错误] 8888 端口被其它程序占用，且不是本软件。
    echo 请先关闭占用程序，或运行 停止.bat 后重试。
    pause
    exit /b 1
)

:: 2. 查找 Chrome / Edge 浏览器
echo [2/4] 检查浏览器...
set "CHROME_PATH="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_PATH if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"

if not defined CHROME_PATH (
    echo [错误] 未找到 Chrome 或 Edge 浏览器
    echo 请安装 Chrome: https://www.google.com/chrome/
    echo.
    pause
    exit /b 1
)
echo       已找到浏览器: %CHROME_PATH%

:: 3. 以调试模式启动 Chrome（v1.x 接管模式需要）
echo [3/4] 启动浏览器调试模式...
if not exist "user-data\chrome-data" mkdir "user-data\chrome-data"
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%~dp0user-data\chrome-data" about:blank
echo       调试端口 9222 已启动
timeout /t 3 /nobreak >nul

:: 4. 启动后端服务（run.py 会再次自检并处理端口占用）
echo [4/4] 启动后端服务...
echo.
echo ========================================
echo   Get Jobs Auto 已启动
echo   管理页面: http://127.0.0.1:8888
echo   API文档:  http://127.0.0.1:8888/docs
echo.
echo   关闭本窗口即可停止服务
echo ========================================
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8888"

"runtime\python.exe" "..\backend\run.py"

pause
