#!/bin/bash
# 用法：./tools/grep_function.sh <函数名>
# 搜索函数定义在哪个文件哪一行（普通函数/类方法/箭头函数）

if [ $# -lt 1 ]; then
    echo "用法: $0 <函数名>"
    exit 1
fi

grep -rn "def $1\|function $1\|$1.*=.*function\|$1.*=>" backend/app frontend/src --include="*.py" --include="*.ts"
