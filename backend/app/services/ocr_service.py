"""
[隐盾] OCR 识别服务 — PaddleOCR 2.x 封装 (CPU)
"""

import re
import cv2
import numpy as np
from typing import Optional
from app.core.config import OCRConfig, SENSITIVE_PATTERNS, SENSITIVE_OBJECT_LABELS


# 类别优先级：具体敏感类型优先于模糊的"地址"类（避免松散地址正则抢命中）
CATEGORY_PRIORITY = {
    "identity": 0,
    "finance": 1,
    "logistics": 2,
    "contact": 3,
    "social": 4,
    "network": 5,
    "location": 6,
}


class OCRService:
    _instance: Optional["OCRService"] = None
    _ocr = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _init_ocr(self):
        if self._ocr is not None:
            return
        from paddleocr import PaddleOCR
        try:
            self._ocr = PaddleOCR(
                lang=OCRConfig.LANG,
                use_angle_cls=True,
                use_gpu=OCRConfig.USE_GPU,   # GPU 加速（Paddle GPU 版）
                show_log=False,
            )
            print(f"[OCR] PaddleOCR ({'GPU' if OCRConfig.USE_GPU else 'CPU'}) 初始化完成")
        except Exception as e:
            print(f"[OCR] GPU 初始化失败，回退 CPU: {e}")
            self._ocr = PaddleOCR(
                lang=OCRConfig.LANG,
                use_angle_cls=True,
                use_gpu=False,
                show_log=False,
            )
            print("[OCR] PaddleOCR (CPU) 初始化完成")

    def detect_text(self, image: np.ndarray, mode: str = "full") -> list[dict]:
        self._init_ocr()
        if self._ocr is None:
            return []

        results = self._ocr.ocr(image, cls=True)
        if not results or not results[0]:
            return []

        regions = []
        for line in results[0]:
            bbox, (text, confidence) = line
            x1, y1 = bbox[0]
            x2, y2 = bbox[2]
            region = {
                "bbox": bbox,
                "rect": {
                    "x": int(min(x1, x2)),
                    "y": int(min(y1, y2)),
                    "w": int(abs(x2 - x1)),
                    "h": int(abs(y2 - y1)),
                },
                "text": text,
                "confidence": float(confidence),
                "sensitive": None,
            }
            if mode == "full":
                region["sensitive"] = self._classify_sensitive(text)
            regions.append(region)

        # 检测框后处理：空白误检丢弃 + 按文字实际边界收紧
        regions = self._tighten_and_filter(image, regions)
        return regions

    def _tighten_and_filter(self, image: np.ndarray, regions: list[dict]) -> list[dict]:
        """检测框贴合文字：低置信度丢弃、空白背景误检丢弃、框向内收紧到文字边界（留 1px 边距）。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        out = []
        for r in regions:
            if r["confidence"] < OCRConfig.MIN_CONFIDENCE:
                continue  # 低置信度误检
            x, y, w, h = r["rect"]["x"], r["rect"]["y"], r["rect"]["w"], r["rect"]["h"]
            if w <= 0 or h <= 0:
                continue
            roi = gray[y:y + h, x:x + w]
            if roi.size == 0:
                continue
            mask = roi < 128  # 暗像素 = 文字"墨水"
            ink_ratio = float(mask.mean())
            if ink_ratio < OCRConfig.MIN_INK_RATIO:
                continue  # 框内几乎无文字 → 空白背景误检
            ys, xs = np.where(mask)
            pad = OCRConfig.BOX_PADDING
            nx0 = max(x, x + int(xs.min()) - pad)
            ny0 = max(y, y + int(ys.min()) - pad)
            nx1 = min(x + w - 1, x + int(xs.max()) + pad)
            ny1 = min(y + h - 1, y + int(ys.max()) + pad)
            r["rect"] = {"x": nx0, "y": ny0, "w": max(1, nx1 - nx0 + 1), "h": max(1, ny1 - ny0 + 1)}
            out.append(r)
        return out

    def _classify_sensitive(self, text: str) -> Optional[dict]:
        # 收集所有命中，按类别优先级选最优（避免"地址"松散正则抢命中）
        hits = []
        for type_name, config in SENSITIVE_PATTERNS.items():
            match = re.search(config["pattern"], text)
            if match:
                hits.append((
                    CATEGORY_PRIORITY.get(config["category"], 9),
                    type_name,
                    config,
                    match,
                ))
        if not hits:
            return None
        hits.sort(key=lambda h: h[0])
        _, type_name, config, match = hits[0]
        return {
            "type": type_name,
            "category": config["category"],
            "risk_level": config["risk_level"],
            "matched_text": match.group(),
            "object_label": SENSITIVE_OBJECT_LABELS.get(config["category"], type_name),
        }

    def filter_sensitive_only(self, regions: list[dict]) -> list[dict]:
        return [r for r in regions if r.get("sensitive") is not None]

    @staticmethod
    def group_by_risk(regions: list[dict]) -> dict:
        groups = {"high": [], "medium": [], "low": [], "none": []}
        for r in regions:
            s = r.get("sensitive")
            groups[s["risk_level"] if s else "none"].append(r)
        return groups
