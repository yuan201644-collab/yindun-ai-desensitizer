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


def test_mobile_pattern_matches_name_adjacent():
    """姓名紧贴手机号（无分隔）→ 命中（Python \\b 对中文不成立会漏检，已修为 (?<![0-9])）"""
    p = SENSITIVE_PATTERNS["手机号"]
    m = re.search(p["pattern"], "柳予威18665533578")
    assert m is not None
    assert m.group() == "18665533578"
    assert m.start() == 3  # 从手机号开始（姓名标签不打码）


def test_mobile_pattern_rejects_digit_padding():
    """长数字串中的片段不命中（前/后视排除数字拼接）"""
    p = SENSITIVE_PATTERNS["手机号"]
    assert not re.search(p["pattern"], "12313800138000")     # 前面有数字
    assert not re.search(p["pattern"], "138001380004567")    # 后面有数字


# ---------- 地址正则强化（前后端同步） ----------

def test_address_strengthened_matches_full_chain():
    p = SENSITIVE_PATTERNS["家庭住址"]
    assert re.search(p["pattern"], "江苏省南京市江宁区东山街道上元大街559")
    assert re.search(p["pattern"], "人民南路10号")
    assert re.search(p["pattern"], "南路10号")
    assert re.search(p["pattern"], "青阳镇人民南路10号")


def test_address_strengthened_no_single_char_false_positive():
    """弱位置词（区/号/栋/室/楼）需 2-6 汉字前缀——「区图书馆」单字触发被挡"""
    p = SENSITIVE_PATTERNS["家庭住址"]
    assert not re.search(p["pattern"], "区图书馆")
    assert not re.search(p["pattern"], "江宁特")
    assert not re.search(p["pattern"], "华意泰富购物广场")
    assert not re.search(p["pattern"], "身份证号码")


def test_address_strengthened_keeps_number_literal():
    """「号码」的「号」不触发（号(?!码)）"""
    p = SENSITIVE_PATTERNS["家庭住址"]
    assert not re.search(p["pattern"], "公民身份号码321324200608290077")


# ---------- 出生日期模式 ----------

def test_birth_date_pattern_matches():
    p = SENSITIVE_PATTERNS["出生日期"]
    assert p["group"] == 1
    m = re.search(p["pattern"], "出生2006年8月29日")
    assert m is not None
    assert m.group(1) == "2006年8月29日"          # 不含「出生」标签
    assert m.start(1) == 2


def test_birth_date_with_space_colon():
    p = SENSITIVE_PATTERNS["出生日期"]
    m = re.search(p["pattern"], "出生：2006 年 8 月 29 日")
    assert m is not None
    assert m.group(1).replace(" ", "") == "2006年8月29日"


def test_birth_date_rejects_label_only():
    p = SENSITIVE_PATTERNS["出生日期"]
    assert not re.search(p["pattern"], "出生")
    assert not re.search(p["pattern"], "出生地 南京")


# ---------- 误报修复：地址机关/城市排除 + QQ 上下文 + 身份证背面 ----------

def test_address_rejects_authority_and_city():
    """「泗洪县公安局」「寄达城市」不误标地址"""
    p = SENSITIVE_PATTERNS["家庭住址"]
    assert not re.search(p["pattern"], "机关泗洪县公安局")
    assert not re.search(p["pattern"], "寄达城市")


def test_address_still_matches_real():
    p = SENSITIVE_PATTERNS["家庭住址"]
    assert re.search(p["pattern"], "江苏省南京市江宁区东山街道上元大街559")
    assert re.search(p["pattern"], "人民南路10号")


def test_qq_requires_context():
    """裸数字（邮编/热线/日期）不标 QQ；QQ 前缀才命中且只取号码"""
    p = SENSITIVE_PATTERNS["QQ号"]
    assert not re.search(p["pattern"], "223900")
    assert not re.search(p["pattern"], "11183")
    m = re.search(p["pattern"], "QQ：12345678")
    assert m is not None
    assert m.group(1) == "12345678"
    assert m.start(1) == 3  # 只打码号码，「QQ：」标签保留


def test_issue_authority_pattern():
    p = SENSITIVE_PATTERNS["签发机关"]
    m = re.search(p["pattern"], "签发机关泗洪县公安局")
    assert m is not None
    assert m.group(1) == "泗洪县公安局"
    assert m.start(1) == 4


def test_validity_period_pattern():
    p = SENSITIVE_PATTERNS["有效期限"]
    m = re.search(p["pattern"], "有效期限2026.08.29-2046.08.29")
    assert m is not None
    assert m.group(1).startswith("2026.08.29")
    assert re.search(p["pattern"], "有效期 长期") is not None


# ---------- 前后端模式库同步清单（必备类型） ----------

SYNC_REQUIRED_TYPES = [
    "姓名", "出生日期", "身份证号", "手机号", "固定电话", "银行卡号",
    "电子邮箱", "家庭住址", "车牌号", "快递单号", "统一社会信用代码", "护照号",
    "签发机关", "有效期限",
]


def test_pattern_library_contains_sync_required_types():
    """与前端 DEFAULT_PATTERNS 对齐的必备类型清单（新增类型需双端同步）"""
    missing = [t for t in SYNC_REQUIRED_TYPES if t not in SENSITIVE_PATTERNS]
    assert missing == [], f"后端模式库缺少必备类型: {missing}"
