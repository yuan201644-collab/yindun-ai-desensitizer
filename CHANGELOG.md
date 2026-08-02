# CHANGELOG

「隐盾」AI 个人信息智能脱敏工具 版本记录

## 版本号规范（沿用 GymFlow 三步判断法）

```
改动进来 → ① 破坏现有用户数据 / 核心交互？
           ├─ 是 → MAJOR（x.0.0）→ 必须用户确认
           └─ 否 → ② 新增用户可见能力？
                   ├─ 是 → MINOR（x.y.0）
                   └─ 否 → PATCH（x.y.z，纯 bug 修复）
```

- 数据格式是分水岭：只增字段 → MINOR；旧数据读不了 / 语义变 → MAJOR
- "优化现有功能" ≠ PATCH；新增用户可见能力入口就是 MINOR
- 拿不准默认往小报（PATCH）；同类能力小幅扩展 → PATCH；实质性新功能 → MINOR
- 版本号只由「用户 + 测试端」指派，开发端（工程师）不得自行 bump
- 大版本（MAJOR）必须用户确认
- 版本常量位置（3 处，发版时同步）：
  - `backend/app/main.py:32`（FastAPI `version`）
  - `backend/app/main.py:90`（根路由 `/` 响应 `version`）
  - `frontend/package.json:3`（`version`）
- 每次发版同步：本文件 + 上述 3 处常量

---

## [1.0.0-alpha] - 2026-08-02

### 新增
- 敏感信息识别新增「统一社会信用代码」（18 位，后端 `SENSITIVE_PATTERNS` + 前端 `DEFAULT_PATTERNS`）
- 敏感信息识别新增「护照号」（E/G + 8 位数字，负向环视正则，兼容中文紧邻语料）
- 后端 `CharacterMaskDesensitizer` 新增护照号掩码分支（保留前 2 后 2，与前端对齐）

### 测试
- 后端 pytest：`test_algorithms`（10）+ `test_text_patterns`（USCC 3 + 护照号 4）
- 前端 vitest：`sensitivePatterns`（11）+ `useDesensitize`（4）
- 全量回归 `./tools/run_all_tests.sh` 通过

### 工作流
- 双 Agent 自动化工作流框架搭建（orchestrator + prompts + tools）
- 时间戳规范：`last_updated` 必须用 `date '+%Y-%m-%d %H:%M'` 取真实时钟
- 测试命令改走 `tools/test_backend.sh` / `tools/test_frontend.sh`，适配 headless 自动运行
