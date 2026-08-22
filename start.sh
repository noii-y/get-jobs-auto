#!/usr/bin/env bash
# Get Jobs Auto - Mac/Linux 启动脚本
set -e

cd "$(dirname "$0")"

echo "========================================"
echo "  Get Jobs Auto 启动中..."
echo "========================================"
echo

# 1. 检测 Python
PYTHON=""
for cmd in python3.12 python3 python; do
    if command -v $cmd &>/dev/null; then
        version=$($cmd --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        if [ "$cmd" = "python3.12" ] || [ "$version" = "3.12" ]; then
            PYTHON=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[错误] 未找到 Python 3.12，请安装 Python 3.12"
    echo "  macOS:   brew install python@3.12"
    echo "  Ubuntu:  sudo apt install python3.12 python3.12-venv"
    exit 1
fi
echo "[1/3] Python: $($PYTHON --version)"

# 2. 检测依赖
if ! $PYTHON -c "import fastapi" 2>/dev/null; then
    echo "[2/3] 安装依赖..."
    $PYTHON -m pip install -r backend/requirements.txt
else
    echo "[2/3] 依赖已安装"
fi

# 3. 检测 Chrome
echo "[3/3] 检测浏览器..."
CHROME_FOUND=0
for path in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/usr/bin/google-chrome" \
    "/usr/bin/google-chrome-stable" \
    "/usr/bin/chromium" \
    "/usr/bin/chromium-browser"; do
    if [ -x "$path" ]; then
        echo "      找到: $path"
        CHROME_FOUND=1
        break
    fi
done
if [ "$CHROME_FOUND" = "0" ]; then
    echo "[警告] 未找到 Chrome/Chromium，请先安装"
    echo "  macOS:   brew install --cask google-chrome"
    echo "  Ubuntu:  sudo apt install google-chrome-stable"
fi

echo
echo "========================================"
echo "  Get Jobs Auto 已启动"
echo "  管理页面: http://127.0.0.1:8888"
echo "  API文档:  http://127.0.0.1:8888/docs"
echo
echo "  按 Ctrl+C 停止服务"
echo "========================================"
echo

# 2秒后自动打开浏览器
(
    sleep 2
    if command -v open &>/dev/null; then
        open http://127.0.0.1:8888
    elif command -v xdg-open &>/dev/null; then
        xdg-open http://127.0.0.1:8888
    fi
) &

cd backend
$PYTHON run.py
