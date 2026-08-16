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


def shrink_rect_to_match(rect: dict, text: str, start: int, end: int) -> dict:
    """按字符等宽比例把整行 rect 收缩为 [start,end) 子串的像素框。

    用于「标签+值」同行场景（如「公民身份号码3213…」）：只保留敏感值的
    像素范围，字段标签不打码。整行即值（start==0 且 end==len）或输入
    无效时原样返回，避免误缩。
    """
    total = len(text or "")
    if total <= 0 or end <= start or start < 0 or end > total or not (start > 0 or end < total):
        return rect
    x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
    x0 = x + int(round(w * start / total))
    x1 = x + int(round(w * end / total))
    return {"x": x0, "y": y, "w": max(1, x1 - x0), "h": h}


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
                s = region["sensitive"]
                # ⭐ 标签+值同行时，把 rect 收缩到敏感子串范围（字段标签不打码）
                if s and s.get("match_start") is not None:
                    region["rect"] = shrink_rect_to_match(
                        region["rect"], text, s["match_start"], s["match_end"]
                    )
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
            pad = OCRConfig.BOX_PADDING
            # ⭐ 主文字带收紧：PaddleOCR 检测框在字段密集单据上常跨多行（快递单实测
            #   「收件人：王伟转袁润熙」框含 3 行墨水）——按"连续墨水带"取墨水总量
            #   最大的带作为文字带（text 所在行墨水最密集），排除邻行与横线。
            row_ink = mask.sum(axis=1) / mask.shape[1]
            has = row_ink > 0.04
            bands = []
            in_b = False
            for i, v in enumerate(has):
                if v and not in_b:
                    in_b = True
                    s = i
                elif not v and in_b:
                    in_b = False
                    bands.append((s, i - 1))
            if in_b:
                bands.append((s, len(has) - 1))
            # ⭐ 合并相邻带（间隙 ≤4 行视为同一文字带）：笔画行间空隙/字间空隙
            #   会把同一行文字切成多个小带；跨行文字行距通常 >4 不会误合并
            merged = []
            for b in bands:
                if merged and b[0] - merged[-1][1] <= 4:
                    merged[-1] = (merged[-1][0], b[1])
                else:
                    merged.append(b)
            bands = merged
            if bands:
                best = max(bands, key=lambda b: float(row_ink[b[0]:b[1] + 1].sum()))
                band_mask = mask[best[0]:best[1] + 1]
                ys = np.where(band_mask.any(axis=1))[0] + best[0]
                xs = np.where(band_mask.any(axis=0))[0]
            else:
                ys, xs = np.where(mask)
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
        # ⭐ 支持条目 group：敏感值取指定捕获组（不含「姓名」等字段标签）
        group_idx = config.get("group")
        if group_idx:
            start, end = match.start(group_idx), match.end(group_idx)
            matched = match.group(group_idx)
        else:
            start, end = match.start(), match.end()
            matched = match.group()
        return {
            "type": type_name,
            "category": config["category"],
            "risk_level": config["risk_level"],
            "matched_text": matched,
            "object_label": SENSITIVE_OBJECT_LABELS.get(config["category"], type_name),
            # 敏感子串在整行文本中的字符区间（图片侧据此只打码内容）
            "match_start": start,
            "match_end": end,
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
