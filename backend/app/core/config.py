"""
================================================================
「隐盾」AI 个人信息智能脱敏工具 - 全局配置
================================================================
所有可配置参数集中管理，方便后续迭代调整。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- 项目根目录 ---
ROOT_DIR = Path(__file__).parent.parent

# --- 服务配置 ---
class ServerConfig:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    WORKERS: int = int(os.getenv("WORKERS", "1"))

# --- GPU 配置 ---
class GPUConfig:
    USE_GPU: bool = os.getenv("USE_GPU", "true").lower() == "true"
    DEVICE: str = "gpu" if USE_GPU else "cpu"
    # 显存限制，防止 OOM
    MEMORY_LIMIT_MB: int = int(os.getenv("GPU_MEMORY_MB", "2048"))

# --- 安全配置 ---
class SecurityConfig:
    MAX_FILE_SIZE_MB: int = 20                    # 上传文件大小上限
    ALLOWED_EXTENSIONS: set = {"png", "jpg", "jpeg", "webp", "bmp"}
    MAX_IMAGE_DIMENSION: int = 4096               # 图片最大边长
    # ⚠️ 核心隐私原则：图片不落盘，仅内存处理
    TEMP_DIR: str = ""                            # 留空=内存处理，填写路径=落盘(调试用)
    RESPONSE_TIMEOUT: int = 60                    # 请求超时(秒)
    # 请求频率限制（滑动窗口）
    RATE_LIMIT_PER_MINUTE: int = 30               # 每 IP 每分钟请求上限
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    # API Key 鉴权（空=关闭，保持零门槛；部署时设 YINDUN_API_KEY 即开启）
    API_KEY: str = os.getenv("YINDUN_API_KEY", "")
    # CORS 白名单（逗号分隔；部署时用 YINDUN_CORS_ORIGINS 配置实际前端域名）
    CORS_ALLOW_ORIGINS: list = [o.strip() for o in os.getenv(
        "YINDUN_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",") if o.strip()]

# --- OCR 配置 ---
class OCRConfig:
    # PaddleOCR 模型选择
    # det: 文本检测 | rec: 文本识别 | cls: 方向分类
    USE_GPU: bool = False                         # GPU 需 cuDNN8 运行库；本机缺 → CPU
    LANG: str = "ch"                              # 中英文混合
    DET_MODEL_DIR: str = ""                       # 留空=自动下载预训练模型
    REC_MODEL_DIR: str = ""
    # 检测精度 (降低可提速)
    DET_DB_THRESH: float = 0.3
    DET_DB_BOX_THRESH: float = 0.5
    # OCR 前下采样目标边长（最长边超过则按比例缩到该值，坐标随后端还原到原图）
    OCR_MAX_SIDE: int = 1600
    # 检测框后处理（贴合文字 + 过滤空白误检）
    MIN_CONFIDENCE: float = 0.45      # 识别置信度下限（低于则丢弃）
    MIN_INK_RATIO: float = 0.01       # 框内"墨水"像素占比下限（空白背景误检）
    BOX_PADDING: int = 1              # 收紧后留 1px 边距贴合文字
    # 识别精度
    REC_BATCH_NUM: int = 6
    # 最大文本长度
    MAX_TEXT_LENGTH: int = 25

# --- 目标检测配置 ---
class DetectionConfig:
    # YOLOv8-nano 模型 (人脸/证件/票据)
    MODEL_NAME: str = "yolov8n.pt"  # 本地文件或自动下载
    # 自定义微调模型路径 (存在则优先加载，否则回退 COCO)
    CUSTOM_MODEL_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../models/yolo_custom.pt")
    CONF_THRESHOLD: float = 0.35                  # 检测置信度阈值
    IOU_THRESHOLD: float = 0.45                   # NMS IoU 阈值
    # 可检测的目标类别 (COCO 通用 + 自定义微调类别)
    SENSITIVE_CLASSES: list = [
        "person", "cell phone", "book",           # COCO 通用
        "id_card", "bank_card", "invoice", "express_slip",  # 自定义微调 (POC 训练)
    ]

# --- 脱敏算法配置 ---
class DesensitizeConfig:
    # 像素化 (马赛克)
    PIXELATE_BLOCK_SIZE: int = 8                  # 马赛克块大小 (越大越模糊)
    # 高斯噪点
    GAUSSIAN_SIGMA_MIN: float = 15.0              # 最小模糊强度
    GAUSSIAN_SIGMA_MAX: float = 45.0              # 最大模糊强度
    GAUSSIAN_NOISE_LEVEL: float = 0.15            # 额外噪点比例
    # 不可逆替换 (核心算法)
    IRREVERSIBLE_SEED_ROUNDS: int = 3             # 随机种子轮次
    IRREVERSIBLE_PATCH_SIZE: int = 4              # 替换块大小
    # 字符掩码
    CHAR_MASK_PATTERN: str = "*"                  # 替换字符
    CHAR_MASK_KEEP_FIRST: int = 3                 # 保留前 N 位
    CHAR_MASK_KEEP_LAST: int = 4                  # 保留后 N 位

# --- 反还原检测配置 ---
class AntiRestoreConfig:
    # SSIM 阈值 (低于此值认为安全)
    SSIM_SAFE_THRESHOLD: float = 0.85
    # PSNR 阈值
    PSNR_SAFE_THRESHOLD: float = 30.0
    # 局部纹理分析块大小
    TEXTURE_PATCH_SIZE: int = 32
    # 检测轮次
    CHECK_ROUNDS: int = 3

# --- 敏感信息正则模式库 ---
# ⚠️ 可扩展：在此添加新的敏感信息类型
SENSITIVE_PATTERNS = {
    "出生日期": {
        "pattern": r"(?:出生)[:：\s]*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?)",
        "category": "identity",
        "risk_level": "medium",
        # ⭐ 敏感值取第 1 捕获组（不含「出生」标签），图片侧只打码日期内容
        "group": 1,
    },
    "姓名": {
        "pattern": r"(?:姓名|名字)[:：\s]*([\u4e00-\u9fa5·]{2,4})(?![0-9])",
        "category": "identity",
        "risk_level": "high",
        # ⭐ 敏感值取第 1 捕获组（不含「姓名」标签），图片侧按子串定位只打码内容
        "group": 1,
    },
    "身份证号": {
        "pattern": r"(?<![0-9])[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9])",
        "category": "identity",
        "risk_level": "high",
    },
    "统一社会信用代码": {
        "pattern": r"\b[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}\b",
        "category": "identity",
        "risk_level": "high",
    },
    "护照号": {
        "pattern": r"(?<![A-Za-z0-9])[EG]\d{8}(?![A-Za-z0-9])",
        "category": "identity",
        "risk_level": "high",
    },
    "手机号": {
        "pattern": r"\b1[3-9]\d{9}\b",
        "category": "contact",
        "risk_level": "high",
    },
    "固定电话": {
        "pattern": r"\b0\d{2,3}-?\d{7,8}\b",
        "category": "contact",
        "risk_level": "medium",
    },
    "银行卡号": {
        "pattern": r"\b(?:62|60|9[0-9]|5[1-5]|4\d)\d{14,17}\b",
        "category": "finance",
        "risk_level": "high",
    },
    "电子邮箱": {
        "pattern": r"\b[\w.-]+@[\w.-]+\.\w{2,}\b",
        "category": "contact",
        "risk_level": "medium",
    },
    "家庭住址": {
        # ⭐ 显式标签前缀（住址/地址/户籍/籍贯等，可选）——标签不进敏感值；
        #   强位置词（省/市/县/镇/乡/村/路/街/道/巷）：1-4 汉字前缀即可；
        #   弱位置词（区/号/栋/室/楼/单元）：要求 2-6 汉字前缀（挡「区图书馆」单字触发）；
        #   号(?!码) 排除「号码/单号」；后缀不吞标点。
        #   group=1 → 敏感值从「江苏」等行政区划名开始，标签（住址/地址）保留
        "pattern": r"(?:家庭住址|常住地址|现住地|住址|地址|户籍|籍贯)?((?:[\u4e00-\u9fa5]{1,4}(?:省|市|县|镇|乡|村|路|街|道|巷)|[\u4e00-\u9fa5]{2,6}(?:区|栋|室|楼|单元))[\u4e00-\u9fa5\d]{0,20})",
        "category": "location",
        "risk_level": "high",
        "group": 1,
    },
    "车牌号": {
        "pattern": r"\b[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼宁][A-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂学警港澳]\b",
        "category": "identity",
        "risk_level": "medium",
    },
    "快递单号": {
        "pattern": r"(?<![A-Za-z0-9])(?:SF|YT|ZTO|STO|YUNDA|JD|DB|DEPPON|EMS)\d{10,18}(?![0-9])",
        "category": "logistics",
        "risk_level": "medium",
    },
    "IP 地址": {
        "pattern": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "category": "network",
        "risk_level": "low",
    },
    "微信号": {
        "pattern": r"\bwxid_[a-zA-Z0-9_-]+\b",
        "category": "social",
        "risk_level": "medium",
    },
    "QQ号": {
        "pattern": r"\b[1-9]\d{4,10}\b",
        "category": "social",
        "risk_level": "low",
        # ⚠️ 备注：此正则会匹配 5-11 位数字，存在误匹配风险（如日期、金额）
        # 实际使用中用户可手动取消选中非敏感区域
    },
}

# --- 敏感对象语义标签 (Part A) ---
# OCR 命中敏感模式时，把区域标记成对应的敏感对象类型（category → 标签）
SENSITIVE_OBJECT_LABELS = {
    "identity": "🪪 证件",
    "contact": "📱 联系方式",
    "finance": "💳 银行卡",
    "location": "📍 地址",
    "logistics": "📦 快递单",
    "network": "🌐 网络",
    "social": "👤 社交账号",
}
