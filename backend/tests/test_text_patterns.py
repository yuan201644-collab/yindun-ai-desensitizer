"""文本敏感模式库测试 — 验证 SENSITIVE_PATTERNS 正则正确性"""
import re

from app.core.config import SENSITIVE_PATTERNS


def test_uscc_pattern_matches_valid():
    p = SENSITIVE_PATTERNS["统一社会信用代码"]
    assert re.search(p["pattern"], "91310000MA1FL4XK9X")
    assert p["category"] == "identity"
    assert p["risk_level"] == "high"


def test_uscc_pattern_rejects_short_text():
    p = SENSITIVE_PATTERNS["统一社会信用代码"]
    assert not re.search(p["pattern"], "91310000")
    assert not re.search(p["pattern"], "12345")


def test_uscc_pattern_matches_within_text():
    p = SENSITIVE_PATTERNS["统一社会信用代码"]
    text = "联系人身份证 11010119900101123X，公司信用代码 91310000MA1FL4XK9X"
    assert re.search(p["pattern"], text)


def test_passport_pattern_matches_valid():
    p = SENSITIVE_PATTERNS["护照号"]
    assert re.search(p["pattern"], "E12345678")
    assert re.search(p["pattern"], "G12345678")
    assert p["category"] == "identity"
    assert p["risk_level"] == "high"


def test_passport_pattern_rejects_short():
    p = SENSITIVE_PATTERNS["护照号"]
    assert not re.search(p["pattern"], "E1234567")
    assert not re.search(p["pattern"], "G12345")


def test_passport_pattern_rejects_wrong_letter():
    p = SENSITIVE_PATTERNS["护照号"]
    assert not re.search(p["pattern"], "A12345678")
    assert not re.search(p["pattern"], "AE12345678")
    assert not re.search(p["pattern"], "E12345678X")
    assert not re.search(p["pattern"], "E123456789")


def test_passport_pattern_matches_within_cn_text():
    p = SENSITIVE_PATTERNS["护照号"]
    text = "我的护照号E12345678，请查收"
    assert re.search(p["pattern"], text)


def test_landline_pattern_matches_valid():
    p = SENSITIVE_PATTERNS["固定电话"]
    assert re.search(p["pattern"], "021-12345678")
    assert re.search(p["pattern"], "02112345678")
    assert re.search(p["pattern"], "010-12345678")
    assert p["category"] == "contact"
    assert p["risk_level"] == "medium"


def test_landline_pattern_rejects_short_and_mobile():
    p = SENSITIVE_PATTERNS["固定电话"]
    assert not re.search(p["pattern"], "0211234")
    assert not re.search(p["pattern"], "13812345678")
