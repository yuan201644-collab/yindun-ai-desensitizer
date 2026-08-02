#!/bin/bash
# 用法：./tools/check_try_catch.sh <文件路径> <行号>
# 检查指定行附近（上下各5行）有多少个 try/catch

if [ $# -lt 2 ]; then
    echo "用法: $0 <文件路径> <行号>"
    exit 1
fi

FILE="$1"
LINE="$2"

if [ ! -f "$FILE" ]; then
    echo "文件不存在: $FILE"
    exit 1
fi

START=$((LINE - 5))
END=$((LINE + 5))
[ $START -lt 1 ] && START=1

COUNT=$(sed -n "${START},${END}p" "$FILE" | grep -cE "try|catch")

echo "${FILE}:${LINE} → 附近try/catch数: ${COUNT}"
