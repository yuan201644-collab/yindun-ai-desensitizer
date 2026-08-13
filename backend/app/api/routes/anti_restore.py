"""
================================================================
「隐盾」API 路由 — 反还原检测端点
================================================================
POST /api/check  — 脱敏强度安全性检测
"""

import cv2
import numpy as np
import base64
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.services.anti_restore_service import AntiRestoreService

router = APIRouter(prefix="/api", tags=["Anti-Restore"])


class StrengthCheckRequest(BaseModel):
    """脱敏强度检测请求"""
    original_image_base64: str = Field(..., description="原始图片 Base64", max_length=30_000_000)
    processed_image_base64: str = Field(..., description="脱敏后图片 Base64", max_length=30_000_000)
    regions: list[dict] = Field(
        default_factory=list,
        description="脱敏区域列表 [{rect: {x, y, w, h}}]"
    )


@router.post("/check")
async def check_strength(req: StrengthCheckRequest):
    """
    ## 脱敏强度核验 ⭐ 特色功能
    对处理后的图片进行 AI 还原风险评估：
    1. SSIM 结构相似度对比
    2. PSNR 峰值信噪比
    3. 纹理熵分析
    4. 综合风险评分 + 加固建议
    """
    # 解码两张图片
    try:
        orig_bytes = base64.b64decode(req.original_image_base64)
        proc_bytes = base64.b64decode(req.processed_image_base64)
        orig = cv2.imdecode(np.frombuffer(orig_bytes, np.uint8), cv2.IMREAD_COLOR)
        proc = cv2.imdecode(np.frombuffer(proc_bytes, np.uint8), cv2.IMREAD_COLOR)
        if orig is None or proc is None:
            raise ValueError("图片解码失败")
    except Exception:
        raise HTTPException(400, "图片 Base64 解码失败")

    # 执行检测
    if req.regions:
        result = AntiRestoreService.check_full_image(orig, proc, req.regions)
    else:
        # 无区域信息 → 全图检测
        result = AntiRestoreService.check_full_image(orig, proc, [{
            "rect": {"x": 0, "y": 0, "w": orig.shape[1], "h": orig.shape[0]}
        }])

    return {
        "success": True,
        **result,
    }
