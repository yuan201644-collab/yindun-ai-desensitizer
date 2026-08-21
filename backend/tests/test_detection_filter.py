"""目标检测 OCR 融合过滤单测 — 核心针对「执照误报 bank_card」"""

from app.services.detection_service import DetectionService as DS


def _obj(x=0, y=0, w=200, h=100, conf=0.87):
    return {"label": "bank_card", "confidence": conf, "rect": {"x": x, "y": y, "w": w, "h": h}}


def _text(txt, cx=100, cy=50):
    return {"rect": {"x": cx - 30, "y": cy - 10, "w": 60, "h": 20}, "text": txt, "bbox": []}


def test_keeps_real_bankcard():
    """真卡：框内识别到 62xx 银联卡号 → 保留"""
    out = DS.filter_by_ocr([_obj()], [_text("6222021234567890123")], 400, 300)
    assert len(out) == 1


def test_keeps_bankcard_with_spaced_cardno():
    """OCR 常把卡号断开成 '6222 0212 3456...'，需去空格后再判"""
    out = DS.filter_by_ocr([_obj()], [_text("6222 0212 3456 7890 123")], 400, 300)
    assert len(out) == 1


def test_drops_license_register_no():
    """营业执照注册号(51…15位)不是银联卡 → 丢弃（用户实测样例 dae152 图）"""
    out = DS.filter_by_ocr([_obj()], [_text("510302000014926")], 400, 300)
    assert len(out) == 0


def test_drops_bankcard_with_no_cardno():
    """框内没有任何文本 → 判误检丢弃"""
    out = DS.filter_by_ocr([_obj()], [], 400, 300)
    assert len(out) == 0


def test_drops_bankcard_with_unrelated_text():
    """框内是执照信息文本、无卡号 → 丢弃"""
    out = DS.filter_by_ocr([_obj()], [_text("自贡市一品堂商贸有限责任公司")], 400, 300)
    assert len(out) == 0


def test_keeps_large_idcard_fallback_rule_unchanged():
    """非 bank_card 对象不受银行卡复查影响（回归）"""
    o = _obj(w=380, h=250)
    o["label"] = "id_card"
    # 小内核文件框面积>60%，但带文本；此用例走原证件规则，不进入银行卡复查
    out = DS.filter_by_ocr([o], [_text("姓名袁润熙")], 400, 300)
    assert len(out) == 0  # 框占94% → 证件规则丢弃（原本行为不变）