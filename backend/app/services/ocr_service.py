"""
[隐盾] OCR 识别服务 — PaddleOCR 2.x 封装 (CPU)
"""

import re
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
