"""Part A 测试：敏感对象语义标签 + 自定义检测类别配置"""
from app.core.config import (
    SENSITIVE_OBJECT_LABELS,
    SENSITIVE_PATTERNS,
    DetectionConfig,
)
from app.services.ocr_service import OCRService


def test_all_pattern_categories_have_object_label():
    """SENSITIVE_PATTERNS 里出现的每个 category 都应有对象标签。"""
    categories = {cfg["category"] for cfg in SENSITIVE_PATTERNS.values()}
    for cat in categories:
        assert cat in SENSITIVE_OBJECT_LABELS, f"category '{cat}' 缺少对象标签"


def test_ocr_classify_returns_object_label():
    svc = OCRService()
    result = svc._classify_sensitive("身份证号11010119900101123X")
    assert result is not None
    assert result["type"] == "身份证号"
    assert result["object_label"] == "🪪 证件"


def test_ocr_classify_express_slip_label():
    svc = OCRService()
    result = svc._classify_sensitive("快递单号SF1234567890123")
    assert result is not None
    assert result["object_label"] == "📦 快递单"


def test_ocr_classify_unknown_returns_none():
    svc = OCRService()
    assert svc._classify_sensitive("今天天气不错") is None


def test_sensitive_classes_include_custom():
    for cls in ["person", "cell phone", "book", "id_card", "bank_card", "invoice", "express_slip"]:
        assert cls in DetectionConfig.SENSITIVE_CLASSES
