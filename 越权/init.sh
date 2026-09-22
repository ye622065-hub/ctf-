#!/bin/bash
# 湖州师范大学校园失物招领系统 —— 容器启动脚本
set -e

echo "[*] 初始化数据库..."
python3 -c "
import sys, os
sys.path.insert(0, '/app')
from app import init_db
init_db()
print('[+] 数据库初始化完成')
"

echo "[*] 启动 Gunicorn..."
exec gunicorn -w 2 -b 0.0.0.0:5000 \
    --access-logfile - \
    --error-logfile - \
    --timeout 60 \
    app:app
