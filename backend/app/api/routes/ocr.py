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


def clamp_rect(rect: dict, img_w: int, img_h: int) -> dict:
    """把 rect 收敛到图片边界内（防 OCR 下采样还原/子串收缩取整导致的 1-2px 超界）"""
    x = max(0, min(rect["x"], img_w - 1))
    y = max(0, min(rect["y"], img_h - 1))
    w = max(1, min(rect["w"], img_w - x))
    h = max(1, min(rect["h"], img_h - y))
    return {"x": x, "y": y, "w": w, "h": h}
from app.core.config import SecurityConfig, OCRConfig

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

    # 3. 尺寸检查：记录原图尺寸，OCR 前下采样提速
    orig_h, orig_w = image.shape[:2]

    # 3.1 OCR 下采样：最长边 > OCR_MAX_SIDE(1600) → 按比例缩到该边长
    #     (比 3.2 的 4096 安全上限更严格，实际先触发；两者共存，4096 仅作兜底)
    scale = 1.0  # 缩放比 = 原边长/缩后边长 (>1)，坐标还原到原图时用
    if max(orig_h, orig_w) > OCRConfig.OCR_MAX_SIDE:
        ratio = OCRConfig.OCR_MAX_SIDE / max(orig_h, orig_w)
        new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
        image = cv2.resize(image, (new_w, new_h))
        scale = max(orig_h, orig_w) / OCRConfig.OCR_MAX_SIDE

    # 3.2 4096 安全上限（兜底）：OCR_MAX_SIDE 下采样后此分支通常不会触发
    h, w = image.shape[:2]
    if max(h, w) > SecurityConfig.MAX_IMAGE_DIMENSION:
        ratio = SecurityConfig.MAX_IMAGE_DIMENSION / max(h, w)
        new_w, new_h = int(w * ratio), int(h * ratio)
        image = cv2.resize(image, (new_w, new_h))
        scale *= 1.0 / ratio  # 叠加进总缩放比

    # 4. OCR 文本检测
    text_regions = ocr_service.detect_text(image, mode=mode)

    # 5. 目标检测 (可选 — 失败不影响 OCR)
    object_regions = []
    if with_detection:
        try:
            detections = detection_service.detect(image)
            object_regions = DetectionService.filter_sensitive(detections)
            # ⭐ OCR 融合过滤：聊天/文档截图被 YOLO 误检为证件（整图框+大量文本）→ 丢弃
            object_regions = DetectionService.filter_by_ocr(object_regions, text_regions, w, h)
        except Exception as e:
            print(f"[OCR] 目标检测跳过 (YOLO 不可用): {e}")

    # 6. 坐标还原：发生过下采样时，把检测框坐标还原到原图坐标系
    # ⚠️ 方案原文写"除以 scale"，但 scale=原边长/缩后边长(>1)，除会进一步缩小；
    #    按方案目标（还原到原图坐标系、前端 overlay 不错位），还原应为乘以 scale。
    if scale != 1.0:
        for region in text_regions + object_regions:
            rect = region.get("rect")
            if rect:
                rect["x"] = int(round(rect["x"] * scale))
                rect["y"] = int(round(rect["y"] * scale))
                rect["w"] = int(round(rect["w"] * scale))
                rect["h"] = int(round(rect["h"] * scale))
            bbox = region.get("bbox")
            if bbox:
                for pt in bbox:
                    pt[0] = int(round(pt[0] * scale))
                    pt[1] = int(round(pt[1] * scale))

    # 6.1 统一收敛到图片边界（防还原/收缩取整超界，前端 overlay 永不越界）
    for region in text_regions + object_regions:
        if region.get("rect"):
            region["rect"] = clamp_rect(region["rect"], orig_w, orig_h)

    # 7. 组装响应
    return {
        "success": True,
        "image_info": {
            "width": orig_w,
            "height": orig_h,
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
