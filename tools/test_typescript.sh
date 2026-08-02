#!/bin/bash
# 一键跑前端 TS 类型检查（vue-tsc --noEmit，内部处理 cd）
cd "$(dirname "$0")/../frontend" || { echo "找不到 frontend/ 目录"; exit 1; }
exec npx vue-tsc --noEmit
