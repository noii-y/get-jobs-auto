@echo off
chcp 65001 >nul
title Get Jobs Auto - 便携版打包工具
cd /d "%~dp0"

echo ========================================
echo   Get Jobs Auto 便携版打包工具
echo ========================================
echo.

set SRC=%~dp0
set DST=%~dp0..\get-jobs-auto-portable

:: 1. 构建前端
echo [1/5] 构建前端...
cd "%SRC%frontend"
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败
    pause
    exit /b 1
)
echo       ✓ 前端构建完成
cd "%SRC%"

:: 2. 复制后端代码
echo [2/5] 复制后端代码...
if not exist "%DST%\backend" mkdir "%DST%\backend"
xcopy /E /I /Y "%SRC%backend\app" "%DST%\backend\app" >nul
copy /Y "%SRC%backend\run.py" "%DST%\backend\run.py" >nul
copy /Y "%SRC%backend\requirements.txt" "%DST%\backend\requirements.txt" >nul
echo       ✓ 后端代码已复制

:: 3. 复制前端构建产物
echo [3/5] 复制前端构建产物...
if not exist "%DST%\frontend\dist" mkdir "%DST%\frontend\dist"
xcopy /E /I /Y "%SRC%frontend\dist\*" "%DST%\frontend\dist" >nul
echo       ✓ 前端产物已复制

:: 4. 更新依赖
echo [4/5] 更新依赖包...
"%DST%\runtime\python.exe" -m pip install --target="%DST%\packages" -r "%DST%\backend\requirements.txt" --upgrade --quiet
if errorlevel 1 (
    echo [警告] 依赖更新可能有问题，请检查
) else (
    echo       ✓ 依赖已更新
)

:: 5. 复制启动脚本和说明
echo [5/5] 复制启动脚本...
copy /Y "%SRC%portable\启动.bat" "%DST%\启动.bat" >nul 2>nul
copy /Y "%SRC%portable\停止.bat" "%DST%\停止.bat" >nul 2>nul
copy /Y "%SRC%portable\README.md" "%DST%\README.md" >nul 2>nul
echo       ✓ 启动脚本已复制

echo.
echo ========================================
echo   打包完成！
echo   输出目录: %DST%
echo ========================================
echo.
pause
