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

### 人性化功能测试修复（P1-P3）
- **P1** 图片页：切换脱敏方法现在同步到所有已选区域（原来改方法不生效、实际用旧算法）
- **P2** 图片页：① 实现拖拽上传（提示文案原本写了"拖拽"却没实现）② OCR 无结果时明确提示"未检测到敏感信息" ③ 去掉"PaddleOCR GPU"误导文案（后端实际 CPU）
- **P3** 图片页：脱敏后可「↩️ 返回选区调整」保留选区；移动端响应式（窄屏纵向布局）
- **P3** 文本页：切换场景模板自动重新检测；「重新处理」不再清空输入文本；示例文本标注适配模板
- **P3** 检测页：单图缺失时提示需传两张；新增「⇄ 交换两张图」

### 图片脱敏页 UX 改进
- 工作区新增「🔄 更换图片 / 🗑️ 删除图片」，导入后可换图/删图（换图自动清空旧检测框）
- 检测后按敏感类别分组（🪪证件/📱联系方式/📦快递单…）显示 chips，**一键全选/取消该类**，含选中数；右上「✔ 全选 / ✖ 取消全选」
- 类别 chips 三态：全选(蓝) / 部分(黄) / 未选(灰)

### 分类系统：重复文字自动创建图片专属分类
- 相同文字出现 ≥3 次 → 自动生成 `📌 文字` 分类（如名单里"信息安全"×30、"男"×21），点击一键全选所有出现该文字的区域
- 与固定敏感分类并存：敏感类型按对象标签（🪪/📱…），重复文字按出现次数
- 无头浏览器实测名单表格：自动生成 计算机学院/信息安全/B240417/男/女 等分类
- 中文标点（、，）保留为合并分隔符

### 识别模式分流引导
- 上传后轻量评估图片复杂度（边缘密度 + 网格线检测）→ simple/medium/complex
- 简单场景：提示"两种模式都可用"；复杂版面（表格/密集文档）：提示"推荐云端识别" + 「改用云端」一键切换按钮
- 纯函数 classifyComplexity 可单测（4 项）；无头浏览器实测名单截图正确判为 complex

### 本地 OCR 修复：hOCR 原始输出兜底
- 用户浏览器实测：Tesseract 读到文字（data.text 有内容）但 data.lines/words 均为空（tesseract.js 词解析在部分浏览器环境失败）
- 修复：recognizeLocal 请求 hOCR 原始输出，words/lines 都空时从 hOCR 解析 ocr_word 词框（坐标+文本+敏感分类）
- 诊断日志 `[localOCR] lines/words/hocr` 辅助定位；OCR 失败不再误显示"未检测到"
- 新增 parseHocr 单测（2 项）

### 本地 OCR 修复：表格/复杂版面 words 回退
- 根因：名单表格等复杂版面 Tesseract 行分组失败（`data.lines` 为空但 `data.words` 有内容），`recognizeLocal` 用了空 lines → 报"未检测到"
- 修复：`data.lines` 为空时回退到 `wordsToRegions`（按词生成区域，表格每格一个独立区域）
- 验证：无头浏览器实测用户提供的名单表格截图，能检测出学号/姓名/学院等文字区域（之前"未检测到"）；新增 wordsToRegions 单测

### 本地 OCR 修复：识别前预处理（提升真实照片识别率）
- 问题：Tesseract 对真实照片/低对比度/小字很弱，同样图片云端能识别、本地"未检测到敏感信息"
- 修复：`recognizeLocal` 喂给 Tesseract 前做预处理——灰度 + 对比度拉伸 + 小图放大（宽<900 放大到 2x），识别框坐标按放大倍数映射回原图
- 验证：无头浏览器实测，含模糊/噪点/旋转的照片风格图也能识别出证件/联系方式；`linesToRegions` 支持 scale 参数
- 诚实说明：Tesseract 中文精度仍低于云端 PaddleOCR，极难图片仍可能失败，建议切云端

### 本地 OCR 修复：资源本地打包（不依赖 CDN）
- 修复本地模式不可用：tesseract.js 默认从 cdn.jsdelivr.net 下载 worker/核心/语言包，国内访问常失败
- 现将全部资源本地打包到 `frontend/public/tesseract/`（worker + core 3 变体 + chi_sim/eng 语言包，约 24MB），浏览器零 CDN 依赖，离线可用
- `localOCR.ts` 的 createWorker 显式指向本地路径；Node 实测识别通过
- 注：本目录体积较大（24MB），为"端侧优先/离线可用"的必要成本

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
