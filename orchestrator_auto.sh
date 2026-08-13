#!/bin/bash
# 隐盾 双Agent工作流协调器（全自动版·方案A：串行调度）v3
# v3 增强：按角色路由模型（planning/testing=Pro / coding=Flash）；默认放弃中间产物 review
# v2 增强：异常恢复 / 可观测性 / 成本控制
# 用法：./orchestrator_auto.sh（在项目根目录 yindun/ 下运行）
# 前提：claude CLI 已装并配置好模型路由；用 -p（headless），跑完即退出

WORKFLOW_DIR=".agent-workflow"
STATUS_FILE="$WORKFLOW_DIR/status.json"
LOG_DIR="$WORKFLOW_DIR/logs"
MAX_ITERATIONS=3
MAX_BUDGET_PER_AGENT=3    # 单 agent 预算上限 USD（防失控，特殊大任务手动调高）
AGENT_TIMEOUT=900         # 单 agent 超时秒数（兜底）
MAX_STALL=3               # 状态连续不变的最大轮数（防热循环）

# 模型路由（CCswitch 已配好）：planning/testing=Pro 架构师 / coding=Flash 工程师
ARCHITECT_MODEL="${ARCHITECT_MODEL:-deepseek-v4-pro[1m]}"
ENGINEER_MODEL="${ENGINEER_MODEL:-deepseek-v4-flash[1m]}"

# 每 phase 卡住判定阈值（分钟）。首次跑可×1.5 缓冲（改这里即可）
declare -A PHASE_STALL_MIN=(
  ["planning"]=20
  ["coding"]=45
  ["testing"]=30
)

mkdir -p "$LOG_DIR"
HISTORY_LOG="$LOG_DIR/history.log"

# ── status.json 读取：jq 优先（无 jq 退回 grep） ──
read_status() {
    local key="$1"
    if command -v jq >/dev/null 2>&1; then
        jq -r ".$key" "$STATUS_FILE" 2>/dev/null || echo ""
    else
        case "$key" in
            phase) grep -o '"phase": *"[^"]*"' "$STATUS_FILE" | head -1 | sed 's/.*: *"//;s/"$//' ;;
            iteration) grep -o '"iteration": *[0-9]*' "$STATUS_FILE" | head -1 | sed 's/.*: *//' ;;
            last_updated) grep -o '"last_updated": *"[^"]*"' "$STATUS_FILE" | head -1 | sed 's/.*: *"//;s/"$//' ;;
        esac
    fi
}

# ── 校验 status.json 可解析（异常恢复：防损坏文件导致硬解失败） ──
# 逐个尝试 jq / python3 / python，任一能解析即通过（注意：Windows Store 的 python3 是占位 stub，不是真 Python）
validate_status() {
    if command -v jq >/dev/null 2>&1 && jq -e '.phase' "$STATUS_FILE" >/dev/null 2>&1; then return 0; fi
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "import json; json.load(open('$STATUS_FILE',encoding='utf-8'))" >/dev/null 2>&1 && return 0
    fi
    if command -v python >/dev/null 2>&1; then
        python -c "import json; json.load(open('$STATUS_FILE',encoding='utf-8'))" >/dev/null 2>&1 && return 0
    fi
    echo "❌ status.json 无法解析（可能损坏）。建议恢复：git checkout -- $STATUS_FILE"
    exit 1
}

get_phase() { read_status phase; }
get_iteration() { read_status iteration; }
get_last_updated() { read_status last_updated; }

# ── 判定当前 phase 是否超时未更新（仅警告，硬截止靠 AGENT_TIMEOUT） ──
phase_stalled() {
    local phase="$1"; local last="$2"
    local limit="${PHASE_STALL_MIN[$phase]:-30}"
    [ -z "$last" ] && return 1
    local epoch; epoch=$(date -d "$last" +%s 2>/dev/null) || return 1
    local now; now=$(date +%s)
    local mins=$(( (now - epoch) / 60 ))
    [ "$mins" -ge "$limit" ]
}

# ── 启动单个 agent（headless，记日志 + 预算 + 耗时） ──
run_agent() {
    local prompt="$1"; local phase="$2"
    local model
    if [ "$phase" = "coding" ]; then model="$ENGINEER_MODEL"; else model="$ARCHITECT_MODEL"; fi
    local iter=$(get_iteration)
    local logfile="$LOG_DIR/iteration-${iter}-${phase}.log"
    echo "[$(date '+%H:%M:%S')] 启动 agent: $prompt (model=$model) → $logfile"
    local start; start=$(date +%s)
    timeout "$AGENT_TIMEOUT" claude -p "$(cat "$WORKFLOW_DIR/$prompt")" \
        --model "$model" \
        --allowedTools "Read Grep Glob Edit Write Bash(git status) Bash(git diff) Bash(git diff *) Bash(git log *) Bash(date) Bash(./tools/*) Bash(bash tools/*) Bash(sh tools/*)" \
        --max-budget-usd "$MAX_BUDGET_PER_AGENT" \
        2>&1 | tee "$logfile"
    local end; end=$(date +%s)
    echo "[$(date '+%H:%M:%S')] agent 完成，耗时 $((end-start))s（预算上限 \$$MAX_BUDGET_PER_AGENT）"
}

# ── phase 切换历史（可观测性） ──
log_history() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] phase=$1 iteration=$2 总耗时=${3}s" >> "$HISTORY_LOG"
}

# ── 失败现场快照（status/plan/test_report/task/git diff 全存） ──
save_failure_snapshot() {
    local snap="$LOG_DIR/failure-$(date '+%Y%m%d-%H%M%S')"
    mkdir -p "$snap"
    cp "$STATUS_FILE" "$snap/" 2>/dev/null
    cp "$WORKFLOW_DIR/plan.md" "$snap/" 2>/dev/null
    cp "$WORKFLOW_DIR/test_report.md" "$snap/" 2>/dev/null
    cp "$WORKFLOW_DIR/task.md" "$snap/" 2>/dev/null
    git diff > "$snap/git.diff" 2>/dev/null
    echo "🕓 失败现场快照已存: $snap"
}

echo "🚀 全自动工作流启动（v2：异常恢复 / 可观测性 / 成本控制）..."
echo ""

PREV_STATUS=""
STALL=0
START=$(date +%s)

while true; do
    validate_status
    PHASE=$(get_phase)
    ITER=$(get_iteration)
    LAST=$(get_last_updated)

    # 迭代上限（启动 agent 前）
    if [ -z "$PHASE" ]; then echo "❌ status.json 读不到 phase"; exit 1; fi
    if [ "$ITER" -gt "$MAX_ITERATIONS" ]; then echo "❌ 超过最大迭代 $MAX_ITERATIONS"; save_failure_snapshot; exit 1; fi

    # 热循环守卫（状态连续不变则计数）
    CUR="$PHASE/$ITER"
    if [ "$CUR" = "$PREV_STATUS" ]; then STALL=$((STALL+1)); else STALL=0; PREV_STATUS="$CUR"; fi
    if [ "$STALL" -ge "$MAX_STALL" ]; then
        echo "❌ 状态连续 $MAX_STALL 轮无变化（可能 agent 卡住/报错），强制停止"
        save_failure_snapshot; exit 1
    fi

    # 当前 phase 超时未更新 → 警告（不强制杀，硬截止靠 AGENT_TIMEOUT）
    if phase_stalled "$PHASE" "$LAST"; then
        echo "⚠️ ${PHASE} 已 ${PHASE_STALL_MIN[$PHASE]} 分钟未更新（可能卡住）。Ctrl+C 人工介入，或让它继续跑（超时兜底 $((AGENT_TIMEOUT/60)) 分钟）。"
    fi

    echo "[$(date '+%H:%M:%S')] 状态: $PHASE | 第 $ITER 轮"

    case $PHASE in
        "planning") run_agent "architect_prompt.md" "$PHASE" ;;
        "coding")   run_agent "engineer_prompt.md" "$PHASE" ;;
        "testing")  run_agent "architect_prompt.md" "$PHASE" ;;
        "done")   log_history done "$ITER" "$(( $(date +%s) - START ))"; echo "✅ 任务完成！第 $ITER 轮"; exit 0 ;;
        "failed") save_failure_snapshot; echo "❌ 迭代超限，需人工介入"; exit 1 ;;
        *) echo "❌ 未知状态: $PHASE"; exit 1 ;;
    esac

    log_history "$PHASE" "$ITER" "$(( $(date +%s) - START ))"
    sleep 3  # 等 agent 落地 status
done
