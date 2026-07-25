"""
================================================================
「隐盾」API 路由 — OCR 识别端点
================================================================
POST /api/ocr
  上传图片 → 检测文本区域 → 敏感信息分类 → 返回标注结果

设计要点：
- 图片仅内存处理，不落盘
- 返回坐标信息，不返回图片数据
- 异步非阻塞
"""

import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.services.ocr_service import OCRService
from app.services.detection_service import DetectionService
from app.core.config import SecurityConfig

router = APIRouter(prefix="/api", tags=["OCR"])

ocr_service = OCRService()
detection_service = DetectionService()


@router.post("/ocr")
async def ocr_detect(
    file: UploadFile = File(..., description="待检测图片 (png/jpg/webp)"),
    mode: str = Query("full", description="检测模式: fast=仅文本 | full=文本+敏感分类"),
    with_detection: bool = Query(True, description="是否同时进行目标检测(人脸/证件)"),
):
    """
    ## 图片敏感区域识别
    - 上传图片，自动检测文字区域并分类敏感信息
    - 可选同时进行 YOLO 目标检测
    - 图片不落盘，响应后即销毁
    """
    # 1. 验证文件
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in SecurityConfig.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式，允许: {SecurityConfig.ALLOWED_EXTENSIONS}")

    contents = await file.read()
    if len(contents) > SecurityConfig.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"文件大小超过 {SecurityConfig.MAX_FILE_SIZE_MB}MB 限制")

    # 2. 解码图片 (内存中)
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "图片解码失败，请检查文件完整性")

    # 3. 尺寸检查
    h, w = image.shape[:2]
    max_dim = max(h, w)
    if max_dim > SecurityConfig.MAX_IMAGE_DIMENSION:
        scale = SecurityConfig.MAX_IMAGE_DIMENSION / max_dim
        new_w, new_h = int(w * scale), int(h * scale)
        image = cv2.resize(image, (new_w, new_h))
        h, w = new_h, new_w

    # 4. OCR 文本检测
    text_regions = ocr_service.detect_text(image, mode=mode)

    # 5. 目标检测 (可选 — 失败不影响 OCR)
    object_regions = []
    if with_detection:
        try:
            detections = detection_service.detect(image)
            object_regions = DetectionService.filter_sensitive(detections)
        except Exception as e:
            print(f"[OCR] 目标检测跳过 (YOLO 不可用): {e}")

    # 6. 组装响应
    return {
        "success": True,
        "image_info": {
            "width": w,
            "height": h,
            # 仅返回扩展名，不暴露用户本地路径
            "format": file.filename.split(".")[-1].lower() if file.filename else "unknown",
        },
        "text_regions": text_regions,
        "object_regions": object_regions,
        "total_sensitive": len([r for r in text_regions if r.get("sensitive")]),
        "statistics": {
            "total_text_boxes": len(text_regions),
            "total_objects": len(object_regions),
            "risk_groups": OCRService.group_by_risk(text_regions),
        },
    }
