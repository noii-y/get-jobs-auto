@echo off
chcp 65001 >nul
title Get Jobs Auto - Chrome Debug Mode

echo ========================================
echo   Get Jobs Auto - Chrome调试模式启动
echo ========================================
echo.

:: 检查Chrome是否已在运行
tasklist /fi "imagename eq chrome.exe" 2>nul | find /i "chrome.exe" >nul
if %errorlevel% equ 0 (
    echo [警告] 检测到Chrome正在运行！
    echo 调试模式需要使用独立的Chrome实例。
    echo 请先关闭所有Chrome窗口，然后重新运行此脚本。
    echo.
    pause
    exit /b 1
)

:: 查找Chrome安装路径
set CHROME_PATH=
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe
) else if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    set CHROME_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
    echo [提示] 未找到Chrome，将使用Microsoft Edge
)

if "%CHROME_PATH%"=="" (
    echo [错误] 未找到Chrome或Edge浏览器！
    echo 请安装Google Chrome后重试。
    pause
    exit /b 1
)

:: 设置用户数据目录
set USER_DATA_DIR=%USERPROFILE%\get-jobs-auto-chrome-profile
if not exist "%USER_DATA_DIR%" mkdir "%USER_DATA_DIR%"

echo [信息] 浏览器路径: %CHROME_PATH%
echo [信息] 数据目录: %USER_DATA_DIR%
echo [信息] 调试端口: 9222
echo.
echo 正在启动浏览器...
echo.

:: 启动调试模式浏览器
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%USER_DATA_DIR%" --disable-blink-features=AutomationControlled

echo [完成] 浏览器已以调试模式启动！
echo.
echo 下一步：
echo   1. 在打开的浏览器中登录 Boss直聘(www.zhipin.com)
echo   2. 登录 51job(www.51job.com)
echo   3. 运行 python run.py 启动后端服务
echo   4. 访问 http://127.0.0.1:8888
echo.
echo 注意：请勿关闭此浏览器窗口，投递工具需要接管它。
echo.
pause
