# 隐盾 (yindun) 开发交接文档

> **用途**：新会话读取此文档即可完整接手「隐盾」项目。包含当前架构、双 Agent 工作流、版本号规范、发布政策、测试方式、踩坑记录。
> **最后更新**：2026-08-19（2.0.0）
> **GitHub**：https://github.com/yuan201644-collab/yindun-ai-desensitizer.git

---

> ⚠️ **版本号规则（开发端必须遵守）**：版本更新只能由「测试/架构（主会话 Claude）」与「用户」共同推动。**开发端（工程师）禁止自行改动版本常量、CHANGELOG、git tag**。你只负责实现功能与修 bug；版本指派、大版本（1→2）确认、发版时机由用户+测试端决定。若发现测试端指派的版本与代码不一致，上报用户，不要自行对齐。

---

## 一、项目简介

「隐盾」是一款面向普通网民/小微商家/校园群体的**零门槛 AI 隐私脱敏工具**（息壤杯·全国人工智能 OPC 创新大赛·惠民产品创新赛道）。上传图片/文本 → 智能识别敏感信息 → 一键脱敏 → 安全分享。核心差异化是**不可逆脱敏算法**（抗 AI 图像还原）+ **脱敏强度检测引擎**。

- **后端**：Python FastAPI（PaddleOCR + YOLOv8-nano + 自研脱敏算法库）
- **前端**：Vue3 + TypeScript（Vite / uni-app 风格，Canvas 端侧处理）
- **隐私原则**：图片不落盘、内存处理、前端端侧优先

**开发节奏**：初赛 2026-08（图片脱敏核心原型）→ 复赛 2026-09（不可逆算法+强度检测+小程序）→ 决赛 2026-11（性能优化+运营商标配）。

---

## 二、版本修改历史

详细见 [CHANGELOG.md](CHANGELOG.md)。当前版本 **2.0.0**（已正式发版）。

| 提交 | 内容 |
|---|---|
| `dfe0f23` | init：项目初始化 |
| `102a436` | 双 Agent 自动化工作流框架搭建 |
| `2532e6f` | feat：新增统一社会信用代码 + 护照号敏感模式 |
| `54b9df3` | chore：工作流时间戳规范 + 测试命令改走 tools 脚本 |

---

## 三、当前架构

```
yindun/
├── frontend/                    # Vue3 + TS（Vite）
│   ├── src/
│   │   ├── pages/               # index(图片脱敏)/text(文本脱敏)/check(强度检测)
│   │   ├── composables/         # useDesensitize / useImageUpload / useOCR / useStrengthCheck
│   │   └── utils/
│   │       ├── canvas.ts        # Canvas 脱敏渲染引擎（端侧）
│   │       ├── api.ts           # API 封装（BASE_URL 可改）
│   │       └── sensitivePatterns.ts  # ★ 前端敏感信息模式库（可扩展）
│   ├── tests/                   # vitest 测试（sensitivePatterns / useDesensitize）
│   └── vitest.config.ts
├── backend/                     # Python FastAPI
│   ├── app/
│   │   ├── main.py              # 入口（version 常量 ×2）
│   │   ├── api/routes/          # ocr / desensitize / anti_restore
│   │   ├── services/            # ocr / detection(YOLO) / desensitize / anti_restore
│   │   └── core/
│   │       ├── config.py        # ★ 全局配置 + SENSITIVE_PATTERNS（可扩展）
│   │       └── algorithms/      # ★ 脱敏算法库（pixelate/gaussian/irreversible/character_mask）
│   ├── tests/                   # pytest 测试（test_algorithms / test_text_patterns）
│   └── requirements.txt / requirements-dev.txt
├── .agent-workflow/             # ★ 双 Agent 状态机（task/plan/test_report/status + prompts）
├── tools/                       # ★ 常用脚本（run_all_tests / test_backend / test_frontend 等）
├── orchestrator.sh              # 半自动协调器
├── orchestrator_auto.sh         # 全自动协调器（claude -p 串行调度）
├── docs/                        # 比赛文档（汇报书/架构/路线图/答辩PPT）
├── CHANGELOG.md                 # 版本记录 + 版本号规范
└── DEVELOPMENT.md               # 本文件
```

### 3.1 脱敏算法库（backend/app/core/algorithms/__init__.py）
- 统一接口：`BaseDesensitizer.apply(image, region, **kwargs)` + `is_irreversible`
- 注册表 `DesensitizerRegistry`：新增算法 `register(name, cls)` 即可
- 四类算法：`pixelate`（马赛克+扰动）/ `gaussian`（多层模糊+噪点）/ `irreversible`（⭐ 种子哈希像素重排，核心创新）/ `CharacterMaskDesensitizer`（文本掩码）

### 3.2 敏感信息模式库（两处需同步）
| 位置 | 说明 |
|---|---|
| `backend/app/core/config.py` → `SENSITIVE_PATTERNS` | 后端识别层，`{pattern, category, risk_level}` |
| `frontend/src/utils/sensitivePatterns.ts` → `DEFAULT_PATTERNS` | 前端模式库，额外含 `keepFirst/keepLast/maskChar` |

**新增敏感类型时必须两端同步**，正则语义保持一致。

---

## 四、双 Agent 工作流（分工已确认）

### 4.1 角色分工
| 角色 | 谁 | 职责 | 不做 |
|---|---|---|---|
| **架构师 = 测试端** | **终端 A（任一模型）** | 写方案 / 补测试 / 跑回归 / 版本指派 / PATCH 本地 commit | 不写业务代码 |
| **工程师 = 开发端** | **终端 B（任一模型）** | 按方案写代码、按测试报告修 bug | 不写测试 / 不跑全量测试 / 不提交 / 不 bump 版本 |
| **推送端** | **终端 A（架构师/测试端）** | GitHub push、MINOR/MAJOR 打包（先问用户） | 版本号由用户+测试端指派 |

### 4.2 双终端模式（主推）— 真·两个终端分工
把两个 Claude Code 终端作为独立会话，分别承担架构师/工程师角色：
- **终端 A**（架构师+测试员）→ `tools/start_architect.sh` 启动
- **终端 B**（工程师）→ `tools/start_engineer.sh` 启动

**模型不写死、不限制**：启动脚本默认不传 `--model`，用 Claude 当前默认模型（任何模型都能跑）；如需指定模型，用环境变量覆盖：
- `ARCHITECT_MODEL=<任意模型> ./tools/start_architect.sh`
- `ENGINEER_MODEL=<任意模型> ./tools/start_engineer.sh`
- 例如用 DeepSeek（经 CCswitch/代理转接）：`ARCHITECT_MODEL=deepseek-v4-pro ./tools/start_architect.sh`，具体模型名以你本机转接配置里可用名称为准。

**交接循环（用户只负责在两头切终端）：**
```
你写 task.md → [终端A] 读status: planning → 写plan.md → phase=coding → 提示去B
            → [终端B] 读status: coding → 按plan写代码 → phase=testing → 提示去A
            → [终端A] 读status: testing → 跑回归写test_report → phase=done/failed 或 回coding
            → 你确认提交/push
```
- 每个终端启动先读 `status.json` 判断该不该自己干；不是自己的阶段就明确提示去对面终端，不越权
- 两个终端共享 `.agent-workflow/` 状态文件做交接，无需互相直接通信

### 4.3 状态机（.agent-workflow/status.json 的 phase）
```
planning → coding → testing → done
                ↘ failed（超过最大迭代）
```
- 人只做两件事：**开头写 task.md**、**结尾确认提交/push** + 在两头切终端
- 双终端手动：`./tools/start_architect.sh` + `./tools/start_engineer.sh`（**默认主推**，见 4.2）
- 单会话直跑（**可选后备**）：主会话 Claude 一个终端即可跑完全流程（写方案→改代码→测试→汇报，代维护 status.json/test_report.md）。不需开两个终端，适合轻量任务或模型/CCswitch 未配置时。本期多数滚动任务即由主会话直跑完成
- 单进程自动：`./orchestrator_auto.sh`（v2：claude -p 串行调度 + 异常恢复[status 损坏防护/断点续跑/卡住警告] + 可观测性[history.log/失败快照] + 成本控制[`--max-budget-usd`] + 热循环守卫 MAX_STALL=3）
- 半自动：`./orchestrator.sh`（按提示切终端）

### 4.4 提示词
- `architect_prompt.md`：规划写方案 / 测试跑回归；只写 `.agent-workflow/` + `tests/`；含双终端交接协议（终端 A）
- `engineer_prompt.md`：只改 `backend/app/**` + `frontend/src/**`；含双终端交接协议（终端 B）
- 两个 prompt 均含**时间戳规则**：`last_updated` 必须用 `date '+%Y-%m-%d %H:%M'` 取

---

## 五、代码规范

### 后端（Python / FastAPI）
- 按现有结构组织：`api/routes/`（端点）、`services/`（业务）、`core/`（配置+算法）
- 新增敏感模式：改 `config.py` 的 `SENSITIVE_PATTERNS`，并在 `frontend` 同步
- 新增算法：`algorithms/` 下继承 `BaseDesensitizer` + `register` 注册
- **不要 `import app.main`**（会触发 PaddleOCR/YOLO 预热，慢）

### 前端（Vue3 + TS）
- 中文 UI 文案；类型标注齐全
- 新增模式：改 `sensitivePatterns.ts` 的 `DEFAULT_PATTERNS`
- 前端脱敏走 `canvas.ts`（端侧，图片不上传）

---

## 六、版本号规范（三步判断法）

> 目的：任何改动进来，先用三步判断定版本；大版本改动必须用户确认。

### 6.1 三步判断法

```
改动进来 → ① 是否破坏现有用户数据 / 核心交互？
           ├─ 是 → MAJOR（第一位 x.0.0）→ 必须用户确认
           └─ 否 → ② 是否新增用户可见能力？
                   ├─ 是 → MINOR（第二位 x.y.0）
                   └─ 否 → PATCH（第三位 x.y.z，bug 修复）
```

### 6.2 各级别判定标准

| 版本位 | 触发条件 | 本项目示例 | 需要确认？ |
|---|---|---|---|
| **MAJOR** `x.0.0` | ① 数据/API 格式不兼容（旧数据读不了 / 需迁移）<br>② 核心主流程重做<br>③ 移除现有功能 | 无先例 | **是** |
| **MINOR** `x.y.0` | 新增用户可见功能 / 入口（向后兼容） | 新增「文本脱敏」页、新增「强度检测」模块 | 否（发版前展示 changelog） |
| **PATCH** `x.y.z` | bug 修复 / 崩溃 / 数据丢失修复<br>同类能力小幅扩展 | 新增敏感类型（USCC/护照号）；小 UI 修复 | 否（例行） |

### 6.3 判定要点
1. **数据格式是分水岭**：只加字段 → MINOR；旧数据读不了 / 语义变 → MAJOR
2. **"优化现有功能" ≠ PATCH**：新增了用户可见入口就是 MINOR；PATCH 只留给"纯修 bug"
3. **拿不准时**：默认往小里报（PATCH），把"是否 MAJOR"的判断交给用户拍板
4. **同类能力小幅扩展 → PATCH**（用户指示 2026-08-02）：如新增敏感类型、小 UI 修复；仅"实质性新功能（新模块/新主交互）"才 MINOR

---

## 七、版本归属与发版清单

### 7.1 版本更新归属（防分歧）
- **谁定版本**：测试/架构（主会话）按三步判断法指派；大版本（1→2）必须用户确认
- **谁改代码**：开发端（工程师）只实现功能，**不改**版本常量 / CHANGELOG / git tag
- **谁验收**：测试端每轮回归检查版本常量是否与指派一致；开发端擅自改或常量滞后 → **上报用户**，不静默对齐

### 7.2 发版清单（每次发版必做）

| 项 | 位置 | 说明 |
|---|---|---|
| `version` | `backend/app/main.py:32` | FastAPI `version` |
| `version` | `backend/app/main.py:90` | 根路由 `/` 响应 `version` |
| `version` | `frontend/package.json:3` | npm `version` |
| `CHANGELOG.md` | 顶部追加 | 记版本 + 改动 |
| `README.md` | 徽章/亮点 | 可选但建议 |

⚠️ 三处常量必须同时同步，缺一处即版本不一致。

---

## 八、发布政策（用户确认 2026-08-02）

| 版本 | 本地 git commit | GitHub push | 打包 |
|---|---|---|---|
| **PATCH**（x.y.z） | ✅ 测试端做 | 不必须 | 不必须 |
| **MINOR**（x.y.0） | ✅ | ✅ VSCode/开发端 | ✅ |
| **MAJOR**（x.0.0） | ✅ | ✅（用户确认） | ✅（用户确认） |
| **紧急 PATCH**（崩溃/丢数据） | ✅ | ✅ 例外允许 | ✅ 例外允许 |

- **分工**：PATCH 由测试端本地 commit；MINOR/MAJOR 由**主会话（架构师/测试端）** commit + push + 打包（push 前先问用户）——VSCode 不再参与 push
- 每次 commit 同步版本常量 + CHANGELOG
- **yindun 打包方式**：前端 `cd frontend && npm run build`（vite dist）；后端 `cd backend && docker build`
- **提交前必须先询问用户确认**，不要默认自动 push

---

## 九、大版本审计

**每个大版本（如迈向 2.0 前）做一次代码审计**：
- XSS / 注入、死代码、未定义引用、版本常量一致性、错误处理
- 审计发现写成报告，修复交给开发端
- **不要脚本批量删死代码**——会括号计数级联误删（GymFlow 踩过），死代码清理人工逐函数

---

## 十、测试资源与环境事实（新 agent 必读 · 防踩坑）

> ⚠️ **本机环境事实**（Windows 开发机，2026-08-18 确认）：
> - **无 bash / 无 WSL**：`./tools/*.sh` 在 PowerShell 里**不能直接跑**（会报 "Cannot run a document" 或路由到未安装的 WSL）。✅ 正确做法：
>   - 后端测试：`Set-Location backend; python -m pytest tests/ -q`
>   - 前端测试：`Set-Location frontend; npm.cmd test`（用 `npm.cmd`，不是 `npm`——ps1 被执行策略挡）
>   - TS 检查：`Set-Location frontend; npx.cmd vue-tsc --noEmit`
> - **PowerShell `Get-ChildItem -Include` 必须配 `-Recurse` 或通配路径**，否则匹配为空（本次排查测试图时踩过，白白浪费时间）。

### 10.0 测试图片位置（重要 · 勿丢）

**全部测试图片在系统截图目录，不在仓库内：`C:\Users\86133\Pictures\Screenshots\`**

6 张标准评测图（对应 `testcases/eval_masking.py`）：

| # | 场景 | 文件名 |
|---|------|--------|
| 1 | 身份证正面 | `ea4f9b378bcf45a38b9959efe380ca7f.jpg` |
| 2 | 身份证背面 | `908bcd8485e50b1890dd3e2a29836a70.jpg` |
| 3 | 聊天截图 | `屏幕截图 2026-08-15 135005.png` |
| 4 | 聊天截图 2 | `屏幕截图 2026-08-16 103218.png` |
| 5 | 快递单 | `5fda231696902dc03ec0deeba87976bc.jpg` |
| 6 | 营业执照 | `dae1525f19f15fb2cfb736ac265b5f0c.jpg` |

完整索引（含大小/用途/安全约束）见 `testcases/测试资源索引.md`。

**⚠️ 安全约束**：以上图片含**真实个人信息**（真实姓名/身份证号），仅限本地测试，禁止进 git、禁止放交付物、禁止上传外部服务。

---

## 十一、测试方式

### 10.1 一键全量
```bash
./tools/run_all_tests.sh   # 后端 pytest + 前端 vitest，汇总 PASS/FAIL
```
- 后端：`./tools/test_backend.sh`（内部 cd 到 backend/，`python -m pytest tests/ -q`）
- 前端：`./tools/test_frontend.sh`（内部 cd 到 frontend/，`npx vitest run`）

### 10.2 测试套件
| 套件 | 位置 | 覆盖 |
|---|---|---|
| `test_algorithms.py` | backend/tests/ | 4 类脱敏算法 + 注册表 + 越界处理 |
| `test_text_patterns.py` | backend/tests/ | SENSITIVE_PATTERNS 正则正确性 |
| `sensitivePatterns.test.ts` | frontend/tests/ | applyMask + 模式库检测 |
| `useDesensitize.test.ts` | frontend/tests/ | 脱敏状态管理（选区/清空/去重） |
| TS 类型检查 `vue-tsc --noEmit` | frontend/tsconfig.json | 全量类型检查（`./tools/test_typescript.sh`） |

### 10.3 测试原则
- 架构师（测试端）维护测试套件，工程师不写测试
- 报告用固定 `[PASS]/[FAIL]` 格式（见 `.agent-workflow/test_report.md` 模板）
- 后端测试**不要 import app.main**（触发模型预热）

---

## 十二、部署与上传

- **后端**：`cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000`（GPU 加 `USE_GPU=true`）
- **前端**：`cd frontend && npm run dev`（或 `npm run build`）
- **Docker**：`cd backend && docker build -t yindun-backend:gpu .`
- **GitHub**：`git add <具体文件> && git commit && git push`（push 前先问用户）
- 远程：`https://github.com/yuan201644-collab/yindun-ai-desensitizer.git`

---

## 十三、踩坑记录

1. **claude CLI 参数（v2.x）**：`--project ./` 和 `--permission-mode acceptEdits` **不支持**（unknown option）。✅ 正确：`claude -p "<prompt>" --allowedTools "Read Grep Glob Edit Write Bash(git status) ..."`；`-p` = headless（跑完即退出）；项目 = 当前目录（先 cd）。
2. **热循环守卫**：全自动脚本必须"状态连续 N 轮不变就强制停止"（`MAX_STALL=3`），否则 agent 报错会无限重发。
3. **迭代上限在启动 agent 前检查**（不是跑完再查）。
4. **headless agent 不能 `rm` 临时文件**：planning 阶段 agent 为了验证会建临时文件，但 `--allowedTools` 无 `rm` → 删不掉，会累积垃圾。**临时验证产物需人工定期清理**。
5. **Python `re` 的 `\b` 对中文不成立**：中文是单词字符，`\b[EG]\d{8}\b` 匹配不了「护照号E12345678」中文紧邻场景。改用负向环视 `(?<![A-Za-z0-9])[EG]\d{8}(?![A-Za-z0-9])`。
6. **pytest 需在 backend/ 下跑**才能 `import app`；用 `tools/test_backend.sh` 处理，别直接裸跑。
7. **PowerShell 跑 bash**：`&&` 是 bash 语法；且 PowerShell 的 `bash` 可能路由到 WSL（没装发行版会报错）。用 git-bash 或 `bash ./脚本.sh`。
8. **status.json 解析**：用 `jq`（无 jq 用 grep fallback，orchestrator 已内置）。
9. **时间戳规范**：agent 更新 `last_updated` 必须用 `date '+%Y-%m-%d %H:%M'` 取真实时钟，否则多 agent 时间戳错乱。
10. **【元信息丢失教训 · 2026-08-18】测试图位置没写进交接文档 → 新 agent 找不到测试图**：项目有 `DEVELOPMENT.md`（设计为"新会话读它即可接手"），但漏记了测试图片位置（实际在 `C:\Users\86133\Pictures\Screenshots\`，不在仓库）。结果新会话排查问题时在 `testcases/` 里找图找不到，浪费大量时间。
    **防复发机制（已落地）**：
    - `DEVELOPMENT.md` 新增「十、测试资源与环境事实」章节，含 6 张测试图清单 + 本机环境事实（无 bash/WSL、PowerShell 特殊性）
    - `testcases/测试资源索引.md` 建立完整资源索引
    - `architect_prompt.md` / `engineer_prompt.md` 的"启动后第一步"已改为**强制先读 DEVELOPMENT.md + status.json + task.md**
    - **教训原则：凡是"换了 agent 就不知道"的项目事实（路径/资源/环境/约束），一律写进 DEVELOPMENT.md；凡是"必须一上来就看的"入口文件，写进 agent prompt 的启动步骤。不要依赖 agent 自己想起来去翻仓库。**

---

## 十四、相关文档

- `README.md` — 用户向项目介绍
- `CHANGELOG.md` — 版本记录 + 版本号规范
- `docs/` — 比赛文档（架构 / 路线图 / 汇报书 / 答辩PPT）
- `AGENT_WORKFLOW_GUIDE.md`（`../健身助手/`）— 双 Agent 工作流通用手册
- `GymFlow改进报告.md`（`../测试gym/` §17）— 版本号规范原始出处
