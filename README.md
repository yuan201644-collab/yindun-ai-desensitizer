# 🛡️ 「隐盾」AI 个人信息智能脱敏工具

> **三步守护你的隐私**：上传 → 脱敏 → 安全分享
>
> 息壤杯 · 全国人工智能 OPC 创新大赛 · 惠民产品创新赛道
>
> 参赛团队：南邮信息安全参赛组（南京邮电大学 · 信息安全专业 · 大二）

---

## 📌 项目简介

「隐盾」是一款面向普通网民、小微商家和校园群体的**零门槛 AI 隐私脱敏工具**。以网页端和微信小程序为载体，一键完成图片和文本中敏感信息的智能识别与安全脱敏。产品完全免费，无需注册登录，三步完成操作。

⭐ **核心差异化**：区别于普通 AI 打码工具，「隐盾」依托信息安全专业背景，自研**不可逆脱敏算法**和**脱敏强度检测引擎**，能有效抵御 AI 图像还原——真正做到"打了码就还原不了"。

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- (推荐) NVIDIA GPU + CUDA 11.8

### 后端启动

```bash
cd backend
pip install -r requirements.txt

# CPU 模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# GPU 模式 (需 CUDA)
USE_GPU=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
cd frontend
npm install
npm run dev:h5
# 访问 http://localhost:5173
```

### Docker 部署 (GPU)

```bash
cd backend
docker build -t yindun-backend:gpu .
docker run --gpus all -p 8000:8000 yindun-backend:gpu
```

---

## 📁 项目结构

```
yindun/
├── frontend/                     # uni-app (Vue 3) 前端
│   └── src/
│       ├── pages/
│       │   ├── index/index.vue   # 图片脱敏主页面
│       │   ├── text/index.vue    # 文本脱敏页面
│       │   └── check/index.vue   # 脱敏强度检测页面
│       ├── components/           # 可复用组件
│       ├── composables/          # 组合式函数 (状态管理)
│       └── utils/
│           ├── canvas.ts         # Canvas 脱敏渲染引擎
│           ├── api.ts            # API 请求封装
│           └── sensitivePatterns.ts  # 敏感信息模式库
├── backend/                      # Python FastAPI 后端
│   └── app/
│       ├── main.py               # 服务入口
│       ├── api/routes/
│       │   ├── ocr.py            # OCR 识别端点
│       │   ├── desensitize.py    # 脱敏处理端点
│       │   └── anti_restore.py   # 反还原检测端点
│       ├── services/
│       │   ├── ocr_service.py    # PaddleOCR 封装
│       │   ├── detection_service.py  # YOLO 目标检测
│       │   ├── desensitize_service.py # 脱敏调度
│       │   └── anti_restore_service.py # 反还原评估
│       └── core/
│           ├── config.py         # 全局配置 (可修改)
│           └── algorithms/       # 脱敏算法库
│               ├── pixelate.py   # 像素化(马赛克)
│               ├── gaussian.py   # 高斯噪点混淆
│               ├── irreversible.py # ⭐ 不可逆替换(核心创新)
│               └── character_mask.py # 字符掩码
├── docs/                         # 📚 文档
│   ├── architecture.md           # 技术架构设计
│   ├── roadmap.md                # 分阶段开发路线图
│   ├── team-plan.md              # 团队分工方案
│   ├── project-report-full.md    # 完整项目汇报书
│   ├── 500-word-intro.md         # 500字项目简介
│   ├── ppt-outline.md            # 答辩PPT大纲(20页)
│   ├── risk-and-deployment.md    # 风险分析 + 落地 + 电信适配
│   └── feature-planning.md       # 全部功能规划
└── README.md                     # 本文件
```

---

## 🔧 核心功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 🖼️ **图片智能脱敏** | OCR + YOLO 识别 → 三种脱敏模式 → 下载 | ✅ |
| 📝 **文本批量脱敏** | 本地正则检测 → 高亮标注 → 一键掩码 | ✅ |
| 🛡️ **脱敏强度检测** ⭐ | SSIM/PSNR/纹理熵 → 风险评分 → 加固建议 | ✅ |
| 🧩 **图片识别增强** | 多行自动聚段、整段一键打码；右侧逐条点选/全选打码；图上 #编号 定位 | ✅ |
| 🧹 **误检融合过滤** | OCR+YOLO 双核对，营业执照不再误报银行卡/证件 | ✅ |

---

## 🎯 可自定义/修改的位置

项目为后续迭代预留了充足的扩展接口：

| 想要... | 去这里修改 |
|---------|-----------|
| 添加新的敏感信息类型 | `backend/app/core/config.py` → `SENSITIVE_PATTERNS` 字典 |
| 添加新的脱敏算法 | `backend/app/core/algorithms/` 下新建 `.py`，继承 `BaseDesensitizer` 并注册 |
| 添加新的前端脱敏模式 | `frontend/src/utils/canvas.ts` → `applyDesensitize()` 中添加 case |
| 添加新的文本敏感模式 | `frontend/src/utils/sensitivePatterns.ts` → `DEFAULT_PATTERNS` 数组 |
| 修改后端服务地址 | `frontend/src/utils/api.ts` → `BASE_URL` 变量 |
| 调整脱敏强度默认值 | `backend/app/core/config.py` → `DesensitizeConfig` 类 |
| 替换 OCR 引擎 | `backend/app/services/ocr_service.py` → 替换 PaddleOCR 实例 |
| 添加新的 API 端点 | `backend/app/api/routes/` 下新建路由文件，在 `main.py` 中注册 |

---

## 📚 文档导航

按角色推荐阅读：

- **所有人** → [项目汇报书](docs/project-report-full.md) | [500字简介](docs/500-word-intro.md)
- **开发者** → [技术架构](docs/architecture.md) | [功能规划](docs/feature-planning.md)
- **项目管理者** → [开发路线图](docs/roadmap.md) | [团队分工](docs/team-plan.md)
- **答辩准备** → [PPT大纲](docs/ppt-outline.md) | [风险与落地](docs/risk-and-deployment.md)

---

## 📅 开发节奏

| 阶段 | 时间 | 目标 |
|------|------|------|
| 🏗️ 初赛 | 2026年8月 | 图片脱敏核心原型 + 演示视频 |
| 🚀 复赛 | 2026年9月 | 不可逆算法 + 强度检测 + 小程序 |
| 🎯 决赛 | 2026年11月 | 性能优化 + 运营商标配方案 |

---

## 👥 团队

- **南京邮电大学 信息安全专业 大二**
- A同学：信息安全方向 — 安全架构 / 脱敏算法 / 反还原检测
- B同学：前端方向 — uni-app / Canvas 引擎 / 交互体验
- C同学：AI 算法方向 — PaddleOCR / YOLO / 后端服务

---

## 📄 License

MIT License — 欢迎社区共建，共同守护大众隐私安全。
