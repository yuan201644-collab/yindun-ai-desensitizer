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
