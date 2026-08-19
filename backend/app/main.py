"""
================================================================
「隐盾」AI 个人信息智能脱敏工具 — FastAPI 主入口 (GPU 版)
================================================================
启动命令：
  # 开发模式
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # 生产模式 (GPU)
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

架构说明：
  识别层 (PaddleOCR GPU + YOLO) → 安全处理层 (脱敏算法库) → 应用层 (FastAPI)
  图片不落盘，所有处理在内存中完成，响应后立即销毁
"""

import traceback
import time

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.ocr import router as ocr_router
from app.core.config import OCRConfig, SecurityConfig
from app.core.security import RateLimitMiddleware, require_api_key
from app.api.routes.desensitize import router as desensitize_router
from app.api.routes.anti_restore import router as anti_restore_router

# --- 应用初始化 ---
app = FastAPI(
    title="「隐盾」AI 脱敏工具 API",
    description="面向大众的轻量化隐私保护工具后端服务",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS (白名单，禁止全开放；部署时用 YINDUN_CORS_ORIGINS 配置实际域名) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=SecurityConfig.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 安全中间件：按 IP 限流（/api/* 除 /api/health；OPTIONS 预检不计入配额） ---
# 注册顺序：CORS 在最外层，限流返回的 429 也能带上 CORS 头，前端可读
app.add_middleware(RateLimitMiddleware)

# --- 注册路由 (模块化，可插拔；API Key 鉴权依赖，默认关闭) ---
app.include_router(ocr_router, dependencies=[Depends(require_api_key)])
app.include_router(desensitize_router, dependencies=[Depends(require_api_key)])
app.include_router(anti_restore_router, dependencies=[Depends(require_api_key)])


# --- 启动事件：预热模型 (YOLO 先加载，避免 DLL 冲突) ---
@app.on_event("startup")
async def warmup_models():
    """启动时预加载模型，避免首次请求等待"""
    try:
        from ultralytics import YOLO
        YOLO("yolov8n.pt", verbose=False)
        print("[Startup] YOLOv8-nano 预热完成")
    except Exception as e:
        print(f"[Startup] YOLO 预热跳过: {e}")

    try:
        from paddleocr import PaddleOCR
        PaddleOCR(lang="ch", use_angle_cls=True, use_gpu=OCRConfig.USE_GPU, show_log=False)
        print("[Startup] PaddleOCR 预热完成")
    except Exception as e:
        print(f"[Startup] PaddleOCR 预热跳过: {e}")


# --- 中间件：请求日志 + 隐私审计 ---
@app.middleware("http")
async def privacy_audit_middleware(request, call_next):
    """记录请求并确保图片数据不泄漏到日志"""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    # ⚠️ 不记录请求体（可能包含图片），仅记录元数据
    response.headers["X-Process-Time"] = str(round(duration, 3))
    response.headers["X-Privacy-Note"] = "in-memory only, no disk storage"
    return response


# --- 根路由 ---
@app.get("/")
async def root():
    return {
        "name": "「隐盾」AI 个人信息智能脱敏工具",
        "version": "2.0.0",
        "status": "running",
        "gpu_available": _check_gpu(),
        "privacy": "端侧优先 · 内存处理 · 不落盘",
    }


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "gpu": _check_gpu(),
        "timestamp": time.time(),
    }


# --- 异常处理 ---
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    # 打印完整堆栈到控制台（不返回给前端，避免信息泄漏）
    print(f"[ERROR] {type(exc).__name__}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "服务内部错误", "type": type(exc).__name__},
    )


def _check_gpu() -> bool:
    """检测 GPU 可用状态"""
    try:
        import paddle
        return paddle.is_compiled_with_cuda()
    except Exception:
        pass
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False
