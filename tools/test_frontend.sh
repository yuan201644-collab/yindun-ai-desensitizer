#!/bin/bash
# 一键跑前端 vitest（内部处理 cd，可在项目根任意位置调用）
cd "$(dirname "$0")/../frontend" || { echo "找不到 frontend/ 目录"; exit 1; }
exec npx vitest run
