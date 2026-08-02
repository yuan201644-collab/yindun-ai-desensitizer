"""对抗还原测试 — 验证 AdversarialService 判定逻辑 + 接入 /api/check 链路"""
import cv2
import numpy as np

from app.core.algorithms import IrreversibleDesensitizer, PixelateDesensitizer
from app.services.adversarial_service import AdversarialService
from app.services.anti_restore_service import AntiRestoreService


def _make_structured_image(h: int = 96, w: int = 128) -> np.ndarray:
    """带结构的图片（模拟文本行）：浅底 + 深色竖/横条，供还原攻击测试。"""
    img = np.full((h, w, 3), 235, dtype=np.uint8)
    for x in range(0, w, 12):
        img[:, x:x + 4] = (40, 40, 40)
    img[30:36, :] = (60, 60, 60)
    img[70:76, :] = (60, 60, 60)
    return img


def _make_checkerboard(h: int = 96, w: int = 128) -> np.ndarray:
    """细棋盘（高频内容）：逐像素交替，供"真被摧毁"的场景测试。"""
    grid = np.indices((h, w)).sum(axis=0) % 2
    gray = (grid * 255).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _region() -> dict:
    return {"x": 8, "y": 8, "w": 64, "h": 64}


def _rois(img: np.ndarray, proc: np.ndarray, r: dict):
    orig_roi = img[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]]
    proc_roi = proc[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]]
    return orig_roi, proc_roi


def test_strong_irreversible_cannot_restore():
    """高频内容被不可逆算法真正摧毁 → 还原攻击失败 → safe。"""
    img = _make_checkerboard()
    r = _region()
    proc = IrreversibleDesensitizer(patch_size=4, rounds=3).apply(img, r)
    orig_roi, proc_roi = _rois(img, proc, r)
    res = AdversarialService.run_attacks(orig_roi, proc_roi)
    assert res["verdict"] == "safe"
    assert res["max_restored_ssim"] <= 0.45
    assert len(res["attacks"]) == 3


def test_adversarial_catches_weak_desensitization():
    """回归测试（记录已知弱点）：低频粗条 + 当前不可逆算法 → 结构保留 → danger。
    算法加固后此断言应翻转为 safe。"""
    img = _make_structured_image()
    r = _region()
    proc = IrreversibleDesensitizer(patch_size=4, rounds=3).apply(img, r)
    orig_roi, proc_roi = _rois(img, proc, r)
    res = AdversarialService.run_attacks(orig_roi, proc_roi)
    assert res["verdict"] == "danger"
    assert res["max_restored_ssim"] > 0.70


def test_deconv_recovers_mild_blur_better_than_destroyed():
    """相对验证：轻微模糊能被反卷积恢复，强脱敏后内容已摧毁无法恢复。"""
    img = _make_structured_image()
    r = _region()
    mild = cv2.GaussianBlur(img, (0, 0), 1.2)
    strong = IrreversibleDesensitizer().apply(img, r)
    orig_roi, proc_roi_mild = _rois(img, mild, r)
    _, proc_roi_strong = _rois(img, strong, r)

    s_mild, _ = AdversarialService._similarity(
        orig_roi, AdversarialService._deblur_attack(proc_roi_mild)
    )
    s_strong, _ = AdversarialService._similarity(
        orig_roi, AdversarialService._deblur_attack(proc_roi_strong)
    )
    assert s_mild > s_strong  # 反卷积对轻模糊更有效


def test_pixelate_verdict_not_danger():
    """强像素化（大块）→ 不应判定 danger。"""
    img = _make_structured_image()
    r = _region()
    proc = PixelateDesensitizer(block_size=12, noise_level=0.1).apply(img, r)
    orig_roi, proc_roi = _rois(img, proc, r)
    res = AdversarialService.run_attacks(orig_roi, proc_roi)
    assert res["verdict"] in ("safe", "warning")


def test_shape_mismatch_auto_align():
    orig = _make_structured_image(96, 128)
    proc = _make_structured_image(90, 120)  # 尺寸不一致，服务应自动对齐
    res = AdversarialService.run_attacks(orig, proc)
    assert res["verdict"] in ("safe", "warning", "danger")


def test_tiny_region_returns_safe():
    orig = np.full((6, 6, 3), 200, dtype=np.uint8)
    proc = np.full((6, 6, 3), 50, dtype=np.uint8)
    res = AdversarialService.run_attacks(orig, proc)
    assert res["verdict"] == "safe"
    assert res["attacks"] == []


def test_check_region_includes_adversarial():
    """接入链路：AntiRestoreService.check_region 返回 adversarial 字段。"""
    img = _make_checkerboard()
    r = _region()
    proc = IrreversibleDesensitizer().apply(img, r)
    orig_roi, proc_roi = _rois(img, proc, r)
    result = AntiRestoreService.check_region(orig_roi, proc_roi)
    assert "adversarial" in result
    assert result["adversarial"]["verdict"] == "safe"
