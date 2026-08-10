"""OCR 检测框后处理测试：贴合文字 + 过滤空白误检"""
import cv2
import numpy as np

from app.services.ocr_service import OCRService


def _make_image() -> np.ndarray:
    img = np.full((200, 400, 3), 245, np.uint8)
    cv2.putText(img, "ZHANG SAN", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2)
    cv2.putText(img, "13800138000", (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2)
    return img


def _region(x: int, y: int, w: int, h: int, conf: float = 0.9) -> dict:
    return {
        "bbox": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
        "rect": {"x": x, "y": y, "w": w, "h": h},
        "text": "t",
        "confidence": conf,
        "sensitive": None,
    }


def test_blank_region_dropped():
    """空白背景上的框（无文字）应被丢弃。"""
    img = _make_image()
    out = OCRService()._tighten_and_filter(img, [_region(300, 150, 80, 30, 0.9)])
    assert out == []


def test_low_confidence_dropped():
    """低置信度框应被丢弃。"""
    img = _make_image()
    out = OCRService()._tighten_and_filter(img, [_region(40, 40, 100, 30, 0.2)])
    assert out == []


def test_loose_box_tightened_to_text():
    """宽松框（向空白扩展）应收紧到文字实际边界。"""
    img = _make_image()
    out = OCRService()._tighten_and_filter(img, [_region(10, 30, 220, 50, 0.9)])
    assert len(out) == 1
    r = out[0]["rect"]
    assert r["x"] >= 35           # 左边不再跑到空白
    assert r["x"] + r["w"] <= 250  # 右边不再超出文字
    assert r["w"] < 220            # 比原宽松框更贴合


def test_real_text_box_kept_and_tight():
    """贴合文字的框被保留并进一步收紧。"""
    img = _make_image()
    out = OCRService()._tighten_and_filter(img, [_region(40, 40, 180, 30, 0.95)])
    assert len(out) == 1
    assert out[0]["rect"]["w"] <= 180
    assert out[0]["rect"]["h"] <= 30
