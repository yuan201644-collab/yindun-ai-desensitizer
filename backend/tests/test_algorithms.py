"""脱敏算法冒烟测试 — 只依赖 cv2 + numpy，不 import app.main（避免触发模型预热）"""
import numpy as np
import pytest

from app.core.algorithms import (
    DesensitizerRegistry,
    PixelateDesensitizer,
    GaussianDesensitizer,
    IrreversibleDesensitizer,
    CharacterMaskDesensitizer,
)

REGION = {"x": 10, "y": 10, "w": 40, "h": 40}
IMG = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)


def _apply_with_shape_check(desensitizer):
    out = desensitizer.apply(IMG, REGION)
    assert out.shape == IMG.shape, "输出图片尺寸必须与原图一致"
    x, y, w, h = REGION["x"], REGION["y"], REGION["w"], REGION["h"]
    assert not np.array_equal(IMG[y:y + h, x:x + w], out[y:y + h, x:x + w]), \
        "脱敏区域像素必须发生改变"
    return out


def test_registry_has_three_algorithms():
    names = DesensitizerRegistry.list_all()
    assert "pixelate" in names
    assert "gaussian" in names
    assert "irreversible" in names


def test_pixelate_changes_region():
    d = PixelateDesensitizer()
    assert d.is_irreversible is True
    _apply_with_shape_check(d)


def test_gaussian_changes_region():
    d = GaussianDesensitizer()
    assert d.is_irreversible is True
    _apply_with_shape_check(d)


def test_irreversible_changes_region():
    d = IrreversibleDesensitizer()
    assert d.is_irreversible is True
    _apply_with_shape_check(d)


def test_irreversible_deterministic_same_region():
    d = IrreversibleDesensitizer()
    out1 = d.apply(IMG, REGION)
    out2 = d.apply(IMG, REGION)
    assert np.array_equal(out1, out2), "同一区域不可逆脱敏结果应可复现"
    assert not np.array_equal(out1, IMG)


def test_unknown_algorithm_raises():
    with pytest.raises(ValueError):
        DesensitizerRegistry.get("does_not_exist")


def test_char_mask_phone():
    cm = CharacterMaskDesensitizer()
    assert cm.mask("13812345678", "手机号") == "138****5678"


def test_char_mask_id_card():
    cm = CharacterMaskDesensitizer()
    raw = "11010119900101123X"
    result = cm.mask(raw, "身份证号")
    assert result.startswith("110")
    assert result.endswith("123X")
    assert len(result) == len(raw)


def test_char_mask_short_text_fully_masked():
    cm = CharacterMaskDesensitizer(keep_first=3, keep_last=4)
    assert cm.mask("abc", "default") == "***"


def test_out_of_bounds_region_safe():
    d = PixelateDesensitizer()
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    out = d.apply(img, {"x": -10, "y": -10, "w": 100, "h": 100})
    assert out.shape == img.shape
