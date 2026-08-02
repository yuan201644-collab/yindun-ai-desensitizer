#!/bin/bash
# 一键跑全部测试套件（后端 pytest + 前端 vitest）

echo "===== 运行全部测试 ====="
echo ""

cd "$(dirname "$0")/.." || { echo "找不到项目根目录"; exit 1; }

PASS=0
FAIL=0

run_test() {
    local name="$1"
    local script="$2"
    echo "--- $name ---"
    if bash "$script"; then
        echo "✅ 通过"
        PASS=$((PASS + 1))
    else
        echo "❌ 失败"
        FAIL=$((FAIL + 1))
    fi
    echo ""
}

# 后端单元测试（脚本内部 cd 到 backend/，才能 import app 包）
run_test "后端 pytest" "tools/test_backend.sh"

# 前端单元测试（脚本内部 cd 到 frontend/）
run_test "前端 vitest" "tools/test_frontend.sh"

echo "===== 测试汇总 ====="
echo "通过: $PASS"
echo "失败: $FAIL"
echo ""

[ $FAIL -eq 0 ] && exit 0 || exit 1
