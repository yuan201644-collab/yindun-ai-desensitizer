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

### 场景模板（方向③ 打样）
- 新增 `scenarioTemplates.ts` 模板注册表：通用 / 快递单 / 聊天记录 / 证件照
- 文本页：选模板只检测该场景相关的敏感类型（如快递单=手机号/固话/地址/单号）
- 图片页：选模板自动选区偏好类型 + 默认脱敏算法/强度（快递单默认不可逆高强）
- 新增快递单示例文本，一键演示；模板逻辑有 vitest 覆盖

### 方向② 本地 OCR 模式（端侧优先 / 隐私卖点）
- 图片页"本地处理"模式从 stub 变为可用：Tesseract.js WASM 浏览器端 OCR（`chi_sim`+`eng`），**图片不出设备**
- 新增 `localOCR.ts`：`linesToRegions` 纯函数（Tesseract line → 区域，与云端结构一致）+ `recognizeLocal`（懒加载、worker 复用）
- `sensitivePatterns.ts` 新增 `OBJECT_LABELS` + `classifyText`（本地敏感分类，含对象标签，与后端对齐）
- 本地模式无 YOLO 对象检测（端侧仅文本识别）；首次识别下载语言包 ~10-15MB
- ⚠️ 诚实标注：本地 Tesseract 中文精度低于云端 PaddleOCR，用户可切云端

### 方向④ 识别层补强（Part A 语义标签 + Part B 自定义检测）
- **Part A**：OCR 敏感区域带对象标签（🪪 证件 / 💳 银行卡 / 📦 快递单等），前端 overlay 显示；分类改为按类别优先级选最优，避免"地址"松散正则抢命中
- **修复**：身份证号 / 快递单号 正则 `\b` 对中文相邻不成立（改用负向环视，同护照号轮）
- **Part B**：自定义检测架构——`SENSITIVE_CLASSES` 扩为 7 类 + 自定义模型存在则加载、否则回退 COCO
- 合成数据集生成器 + GPU 训练脚本；装 CUDA torch（2.6.0+cu124），RTX 4060 训 POC 模型 **mAP50=0.995**
- ⚠️ **POC 局限**：合成数据类别靠细微色差区分，未见过的卡类别判别弱（易判成 bank_card）；检测对象本身高置信。真实标注数据 + 再训后类别精度提升。训练链路已打通。

### 对抗还原测试（方向① 轻量版）
- 新增 `AdversarialService`：对脱敏区域跑 3 种还原攻击（超分插值 / Richardson-Lucy 去模糊 / 边缘增强），测"还原后与原图"的 SSIM/PSNR
- `/api/check` 响应新增 `region_details[].adversarial` 与 `adversarial_summary`（safe/warning/danger 判定 + 卖点文案）
- 强度检测页新增「🧪 对抗还原测试」展示区（攻击结果表 + 抗还原判定）
- 纯经典算法实现，无新依赖；接口预留接入 Real-ESRGAN 等真超分模型
- ⚠️ 已知发现：当前不可逆算法对**低频均匀区域**（粗块）结构保留、可被还原（SSIM≈0.81）；对**细笔画文本**（证件/票据文字）有效（SSIM≈0.33）。已在测试中固化为回归用例
