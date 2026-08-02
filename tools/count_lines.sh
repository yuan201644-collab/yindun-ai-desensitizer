#!/bin/bash
# 用法：./tools/count_lines.sh [文件或目录]
# 统计代码行数。不传参数 = 统计项目全部源码（py/ts/vue/js）
# 传文件 = 该文件行数；传目录 = 目录下 py/ts/vue/js 行数合计

if [ $# -ge 1 ]; then
    TARGET="$1"
    if [ -f "$TARGET" ]; then
        wc -l "$TARGET"
    elif [ -d "$TARGET" ]; then
        find "$TARGET" \( -name "*.py" -o -name "*.ts" -o -name "*.vue" -o -name "*.js" \) | xargs wc -l | tail -1
    else
        echo "路径不存在: $TARGET"
        exit 1
    fi
    exit 0
fi

# 默认：项目源码（不含 node_modules / tests / 工作流目录）
find . -path ./node_modules -prune -o -path ./frontend/node_modules -prune -o \
  \( -name "*.py" -o -name "*.ts" -o -name "*.vue" -o -name "*.js" \) -print 2>/dev/null \
  | grep -v "/node_modules/" | grep -v "/tests/" | grep -v "/.agent-workflow/" \
  | xargs wc -l | tail -1
