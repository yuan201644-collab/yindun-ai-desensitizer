#!/bin/bash
# 一键跑后端 pytest（内部处理 cd，可在项目根任意位置调用）
cd "$(dirname "$0")/../backend" || { echo "找不到 backend/ 目录"; exit 1; }
exec python -m pytest tests/ -q
