"""
「隐盾」身份证字段脱敏测试 — 只打码内容、保留字段标签
=====================================================
覆盖：
1. _classify_sensitive 子串定位（match_start/match_end + group 支持）
2. shrink_rect_to_match 纯函数（整行不缩 / 子串比例 / 边界安全）
3. detect_and_mask_text（文本脱敏也只掩码值、不掩码标签）
⚠️ 不 import app.main（不触发模型预热）；_classify_sensitive 纯正则逻辑，不初始化 PaddleOCR
"""

import pytest

from app.services.ocr_service import OCRService, shrink_rect_to_match
from app.services.desensitize_service import DesensitizeService


@pytest.fixture(scope="module")
def svc():
    """仅用分类/收缩逻辑，不触发 _init_ocr（PaddleOCR）"""
    return OCRService()


# ==================== 1. _classify_sensitive 子串定位 ====================

class TestClassifySubstring:
    ID18 = "32132420060829007X"  # 合法 18 位身份证号（格式级）

    def test_idcard_number_excludes_label(self, svc):
        s = svc._classify_sensitive(f"公民身份号码{self.ID18}")
        assert s is not None
        assert s["type"] == "身份证号"
        assert s["matched_text"] == self.ID18                     # 不含「公民身份号码」
        assert s["match_start"] == 6                              # 子串起始在标签之后
        assert s["match_end"] == len(f"公民身份号码{self.ID18}")

    def test_idcard_label_not_mistaken_as_address(self, svc):
        """「身份号码」的「号」不得触发地址正则（含残缺 OCR 行）"""
        s = svc._classify_sensitive(f"公民身份号码{self.ID18}")
        assert s["type"] == "身份证号"                            # 优先类别正确
        # 17 位残缺行：身份证不命中，也不得被「号」误标为家庭住址
        assert svc._classify_sensitive("公民身份号码32132420060829007") is None

    def test_name_excludes_label(self, svc):
        s = svc._classify_sensitive("姓名：袁润熙")
        assert s is not None
        assert s["type"] == "姓名"
        assert s["matched_text"] == "袁润熙"                       # group=1，不含「姓名：」
        assert s["match_start"] == 3
        assert s["match_end"] == 6

    def test_name_with_space_separator(self, svc):
        """PaddleOCR 常见输出：标签与值间带空格"""
        s = svc._classify_sensitive("姓名 袁润熙")
        assert s is not None
        assert s["matched_text"] == "袁润熙"
        assert s["match_start"] == 3

    def test_name_two_chars(self, svc):
        s = svc._classify_sensitive("姓名：张三")
        assert s is not None
        assert s["matched_text"] == "张三"
        assert s["match_start"] == 3

    def test_address_excludes_label(self, svc):
        s = svc._classify_sensitive("住址：江苏省泗洪县青阳镇人民南路10号")
        assert s is not None
        assert s["type"] == "家庭住址"
        # ⭐ 强化后地址正则从「江苏省」起匹配（「江苏」+「省」），标签「住址：」保留
        assert s["matched_text"].startswith("江苏省")
        assert "人民南路10号" in s["matched_text"]          # ⭐ group 须含完整地址（后缀），防只匹配位置词
        assert s["match_start"] == 3
        assert "住址：" not in s["matched_text"]

    def test_pure_label_lines_not_sensitive(self, svc):
        """纯标签行（性别/民族）不误伤"""
        assert svc._classify_sensitive("性别 男") is None
        assert svc._classify_sensitive("民族 汉") is None
        assert svc._classify_sensitive("出生") is None

    def test_full_line_value_no_shrink_marker(self, svc):
        """整行就是敏感值时，match 覆盖整行（无前缀标签）"""
        s = svc._classify_sensitive(self.ID18)
        assert s is not None
        assert s["match_start"] == 0
        assert s["match_end"] == 18

    def test_birth_date_excludes_label(self, svc):
        """出生日期：只定位日期值，不含「出生」标签"""
        s = svc._classify_sensitive("出生2006年8月29日")
        assert s is not None
        assert s["type"] == "出生日期"
        assert s["matched_text"] == "2006年8月29日"
        assert s["match_start"] == 2
        assert s["match_end"] == len("出生2006年8月29日")

    def test_birth_date_with_space_and_colon(self, svc):
        s = svc._classify_sensitive("出生：2006 年 8 月 29 日")
        assert s is not None
        assert s["matched_text"].replace(" ", "") == "2006年8月29日"
        assert s["match_start"] == 3

    def test_birth_label_alone_not_sensitive(self, svc):
        assert svc._classify_sensitive("出生") is None
        assert svc._classify_sensitive("出生地 南京") is None  # 无日期数字 → 不命中

    def test_address_no_single_char_false_positive(self, svc):
        """强化后：单字位置词不误报（「区图书馆」等）"""
        assert svc._classify_sensitive("区图书馆") is None
        assert svc._classify_sensitive("江宁特") is None
        assert svc._classify_sensitive("华意泰富购物广场") is None

    def test_address_short_suffix_line(self, svc):
        """分行地址第二行（无前缀）也能命中（「南路」+「路」强词分支）"""
        s = svc._classify_sensitive("南路10号")
        assert s is not None
        assert s["type"] == "家庭住址"

    def test_address_no_colon_label_kept(self, svc):
        """真实 OCR 无冒号（「住址江苏省…」）：标签「住址」不进敏感值（group=1 定位）"""
        s = svc._classify_sensitive("住址江苏省泗洪县青阳镇人民")
        assert s is not None
        assert s["type"] == "家庭住址"
        assert s["matched_text"].startswith("江苏省")            # 「住址」标签不在打码范围
        assert "泗洪县青阳镇" in s["matched_text"]               # ⭐ 完整地址内容
        assert "住址" not in s["matched_text"]
        assert s["match_start"] == 2


# ==================== 2. shrink_rect_to_match 纯函数 ====================

class TestShrinkRect:
    RECT = {"x": 100, "y": 200, "w": 240, "h": 30}

    def test_full_line_no_shrink(self):
        """start==0 且 end==len → 原样返回"""
        assert shrink_rect_to_match(dict(self.RECT), "32132420060829007X", 0, 18) == self.RECT

    def test_substring_ratio(self):
        """「公民身份号码3213…」24 字符，值 18 字符从第 6 字符起 → x 收缩到 25% 起"""
        text = "公民身份号码32132420060829007X"
        got = shrink_rect_to_match(dict(self.RECT), text, 6, 24)
        assert got["x"] == 100 + round(240 * 6 / 24)               # 160
        assert got["w"] == round(240 * 18 / 24)                    # 180
        assert got["y"] == 200 and got["h"] == 30                  # 高度不变

    def test_label_prefix(self):
        """「姓名：袁润熙」只收缩到值部分（后 3 字符）"""
        text = "姓名：袁润熙"
        got = shrink_rect_to_match(dict(self.RECT), text, 3, 6)
        assert got["x"] == 100 + round(240 * 3 / 6)                # 220
        assert got["w"] == round(240 * 3 / 6)                      # 120

    def test_empty_or_invalid(self):
        assert shrink_rect_to_match(dict(self.RECT), "", 0, 0) == self.RECT
        assert shrink_rect_to_match(dict(self.RECT), "abc", 2, 2) == self.RECT   # end<=start
        assert shrink_rect_to_match(dict(self.RECT), "abc", -1, 2) == self.RECT  # start<0
        assert shrink_rect_to_match(dict(self.RECT), "abc", 0, 99) == self.RECT  # end>total


# ==================== 3. detect_and_mask_text（文本脱敏） ====================

class TestDetectAndMaskText:
    def test_name_masked_value_only(self):
        masked, spans = DesensitizeService.detect_and_mask_text("姓名：袁润熙")
        assert "姓名：" in masked                                 # 标签保留
        assert "袁润熙" not in masked                              # 值被掩码
        assert len(spans) == 1
        assert spans[0]["start"] == 3 and spans[0]["end"] == 6

    def test_mixed_text_labels_kept(self):
        masked, spans = DesensitizeService.detect_and_mask_text(
            "姓名：袁润熙 电话：13800138000"
        )
        assert "姓名：" in masked and "电话：" in masked           # 两个标签都保留
        assert "13800138000" not in masked                          # 手机号被掩码
        assert "袁润熙" not in masked
        assert len(spans) == 2

    def test_plain_id_number(self):
        masked, spans = DesensitizeService.detect_and_mask_text("证件号32132420060829007X")
        assert "证件号" in masked                                   # 非标准前缀保留
        assert "32132420060829007X" not in masked
