"""
[隐盾] OCR 识别服务 — PaddleOCR 2.x 封装 (CPU)
"""

import re
import numpy as np
from typing import Optional
from app.core.config import OCRConfig, SENSITIVE_PATTERNS


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
        self._ocr = PaddleOCR(
            lang=OCRConfig.LANG,
            use_angle_cls=True,
            use_gpu=False,          # CPU 模式，最稳定
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
        return regions

    def _classify_sensitive(self, text: str) -> Optional[dict]:
        for type_name, config in SENSITIVE_PATTERNS.items():
            match = re.search(config["pattern"], text)
            if match:
                return {
                    "type": type_name,
                    "category": config["category"],
                    "risk_level": config["risk_level"],
                    "matched_text": match.group(),
                }
        return None

    def filter_sensitive_only(self, regions: list[dict]) -> list[dict]:
        return [r for r in regions if r.get("sensitive") is not None]

    @staticmethod
    def group_by_risk(regions: list[dict]) -> dict:
        groups = {"high": [], "medium": [], "low": [], "none": []}
        for r in regions:
            s = r.get("sensitive")
            groups[s["risk_level"] if s else "none"].append(r)
        return groups
