"""
「隐盾」YOLO 对象检测 OCR 融合过滤测试
=====================================
覆盖 filter_by_ocr：聊天/文档截图整图误检为证件 → 过滤；真证件（小面积框）保留。
⚠️ 纯逻辑单测，不 import app.main、不触发 YOLO 模型。
"""

import pytest

from app.services.detection_service import DetectionService


def _obj(x, y, w, h, label="id_card", conf=0.78):
    return {"label": label, "confidence": conf, "rect": {"x": x, "y": y, "w": w, "h": h}}


def _text(x, y, w=100, h=20):
    return {"rect": {"x": x, "y": y, "w": w, "h": h}, "text": "x", "sensitive": None}


class TestFilterByOcr:
    def test_chat_screenshot_full_frame_filtered(self):
        """聊天截图场景：框占图 90% + 内部 14 行文本 → 误检过滤"""
        img_w, img_h = 1270, 814
        objs = [_obj(0, 0, 1176, 791, "id_card", 0.78)]           # 面积占比 ≈ 89.7%
        texts = [_text(30 + i * 10, 50 + i * 40) for i in range(14)]  # 14 行都在框内
        out = DetectionService.filter_by_ocr(objs, texts, img_w, img_h)
        assert out == []

    def test_real_idcard_kept(self):
        """真证件场景：框占图 ~11%（右半卡片）+ 内部 3 行文本 → 保留"""
        img_w, img_h = 826, 1304
        objs = [_obj(885, 144, 256, 458, "bank_card", 0.94)]      # 面积占比 ≈ 10.9%
        texts = [_text(900, 200 + i * 60, 200, 30) for i in range(3)]
        out = DetectionService.filter_by_ocr(objs, texts, img_w, img_h)
        assert len(out) == 1
        assert out[0]["label"] == "bank_card"

    def test_medium_box_not_filtered(self):
        """面积占比 50%（<0.8）+ 内部 8 行文本 → 保留（阈值边界）"""
        img_w, img_h = 1000, 1000
        objs = [_obj(250, 250, 500, 500)]                         # 25% 面积
        texts = [_text(300, 300 + i * 50, 300, 20) for i in range(8)]
        assert len(DetectionService.filter_by_ocr(objs, texts, img_w, img_h)) == 1

    def test_large_area_but_few_text_kept(self):
        """框占图 90% 但内部文本 <5 行（可能为真卡片特写）→ 保留"""
        img_w, img_h = 1000, 1000
        objs = [_obj(0, 0, 900, 900)]
        texts = [_text(100, 100 + i * 200, 400, 20) for i in range(2)]
        assert len(DetectionService.filter_by_ocr(objs, texts, img_w, img_h)) == 1

    def test_empty_and_invalid_safe(self):
        assert DetectionService.filter_by_ocr([], [], 100, 100) == []
        bad = [{"label": "x", "rect": {"x": 0, "y": 0, "w": 0, "h": 0}}]
        assert DetectionService.filter_by_ocr(bad, [], 100, 100) == []
        no_rect = [{"label": "x"}]
        assert DetectionService.filter_by_ocr(no_rect, [], 100, 100) == []
