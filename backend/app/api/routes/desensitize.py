"""
================================================================
「隐盾」API 路由 — 脱敏处理端点
================================================================
POST /api/desensitize/image  — 图片脱敏（服务端增强模式）
POST /api/desensitize/text    — 文本脱敏
"""

import cv2
import numpy as np
import base64
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services.desensitize_service import DesensitizeService

router = APIRouter(prefix="/api/desensitize", tags=["Desensitize"])


# --- 请求模型 ---

class ImageDesensitizeRequest(BaseModel):
    """图片脱敏请求"""
    image_base64: str = Field(..., description="Base64 编码的图片")
    regions: list[dict] = Field(..., description="脱敏区域列表")
    default_method: str = Field(
        default="pixelate",
        description="默认脱敏算法: pixelate | gaussian | irreversible"
    )
    # 算法参数 (可选，用于调整强度)
    pixelate_block_size: Optional[int] = Field(default=8, ge=2, le=64)
    gaussian_sigma: Optional[float] = Field(default=25.0, ge=5.0, le=100.0)
    irreversible_rounds: Optional[int] = Field(default=3, ge=1, le=10)


class TextDesensitizeRequest(BaseModel):
    """文本脱敏请求"""
    text: str = Field(..., description="原始文本", min_length=1, max_length=50000)
    custom_patterns: Optional[list[dict]] = Field(
        default=None,
        description="自定义敏感词/模式列表 [{\"pattern\": \"regex\", \"type\": \"example\"}]"
    )


# --- 路由 ---

@router.post("/image")
async def desensitize_image(req: ImageDesensitizeRequest):
    """
    ## 图片脱敏（服务端增强模式）
    用于大文件或复杂脱敏场景，前端 Canvas 处理有性能压力时使用。
    优先推荐前端本地脱敏以保护隐私。
    """
    # 1. 解码图片
    try:
        img_bytes = base64.b64decode(req.image_base64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("解码失败")
    except Exception:
        raise HTTPException(400, "图片 Base64 解码失败")

    # 2. 应用脱敏
    kwargs = {}
    if req.default_method == "pixelate":
        kwargs["block_size"] = req.pixelate_block_size
    elif req.default_method == "gaussian":
        kwargs["sigma"] = req.gaussian_sigma
    elif req.default_method == "irreversible":
        kwargs["rounds"] = req.irreversible_rounds

    result = DesensitizeService.process_image(
        image, req.regions, method=req.default_method, **kwargs
    )

    # 3. 编码返回
    _, buffer = cv2.imencode(".png", result)
    result_b64 = base64.b64encode(buffer).decode("utf-8")

    return {
        "success": True,
        "processed_image_base64": result_b64,
        "method_used": req.default_method,
        "regions_processed": len(req.regions),
    }


@router.post("/text")
async def desensitize_text(req: TextDesensitizeRequest):
    """
    ## 文本批量脱敏
    自动检测文本中的敏感信息并掩码处理。
    - 支持 10+ 类内置敏感模式
    - 支持自定义敏感词/正则
    """
    masked_text, spans = DesensitizeService.detect_and_mask_text(req.text)

    return {
        "success": True,
        "original_text": req.text,
        "masked_text": masked_text,
        "sensitive_spans": spans,
        "total_sensitive": len(spans),
        "statistics": {
            "by_risk": {
                "high": len([s for s in spans if s.get("risk_level") == "high"]),
                "medium": len([s for s in spans if s.get("risk_level") == "medium"]),
                "low": len([s for s in spans if s.get("risk_level") == "low"]),
            }
        },
    }
