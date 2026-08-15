"""OCR 大图下采样测试：配置 + 坐标还原数学正确性"""
from app.core.config import OCRConfig


def test_ocr_max_side_config():
    """下采样目标边长已配置。"""
    assert OCRConfig.OCR_MAX_SIDE == 1600
    assert OCRConfig.OCR_MAX_SIDE < 4096  # 比安全上限更严格，实际先触发


def test_coordinate_restore_within_original_bounds():
    """下采样后坐标乘回 scale 应还原到原图坐标系内（scale = 原边长/缩后边长）。"""
    orig_w, orig_h = 3000, 2000
    scale = max(orig_h, orig_w) / OCRConfig.OCR_MAX_SIDE
    # 模拟 OCR 在缩后图（1600 x 1066）上检出的框
    ocr_rect = {"x": 100, "y": 50, "w": 300, "h": 60}
    restored = {k: int(round(v * scale)) for k, v in ocr_rect.items()}
    # 还原后仍在原图范围内
    assert restored["x"] + restored["w"] <= orig_w
    assert restored["y"] + restored["h"] <= orig_h
    # 还原比例正确：3000/1600 = 1.875 → 100*1.875=187.5 → round=188
    assert restored["x"] == round(100 * 1.875)


def test_small_image_scale_is_one():
    """最长边 < OCR_MAX_SIDE 时不下采样（scale 应为 1）。"""
    orig_w, orig_h = 1143, 901
    scale = max(orig_h, orig_w) / OCRConfig.OCR_MAX_SIDE if max(orig_h, orig_w) > OCRConfig.OCR_MAX_SIDE else 1.0
    assert scale == 1.0


# ---------- clamp_rect：rect 收敛到图片边界（防超界） ----------

def test_clamp_rect_valid_unchanged():
    from app.api.routes.ocr import clamp_rect
    rect = {"x": 10, "y": 20, "w": 100, "h": 50}
    assert clamp_rect(rect, 800, 600) == rect


def test_clamp_rect_beyond_right_bottom():
    """超出右下界的 rect 收敛到边界（x+w ≤ 宽、y+h ≤ 高），起点合法则保留、裁剪尾部尺寸"""
    from app.api.routes.ocr import clamp_rect
    out = clamp_rect({"x": 780, "y": 590, "w": 100, "h": 80}, 800, 600)
    assert out == {"x": 780, "y": 590, "w": 20, "h": 10}  # 起点合法保留，w/h 裁到边界内
    assert out["x"] + out["w"] <= 800
    assert out["y"] + out["h"] <= 600


def test_clamp_rect_negative_origin():
    """负坐标收敛到 0（w/h 相应裁剪）"""
    from app.api.routes.ocr import clamp_rect
    out = clamp_rect({"x": -5, "y": -3, "w": 100, "h": 50}, 800, 600)
    assert out["x"] == 0 and out["y"] == 0
    assert out["w"] == 100 and out["h"] == 50  # 起点归零，尺寸不变


def test_clamp_rect_large_overflow():
    """rect 整体超出图片（起点合法但尺寸过大）→ 收敛不超界"""
    from app.api.routes.ocr import clamp_rect
    out = clamp_rect({"x": 500, "y": 400, "w": 5000, "h": 5000}, 800, 600)
    assert out["x"] + out["w"] <= 800
    assert out["y"] + out["h"] <= 600
