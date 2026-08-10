"""脱敏算法区域级强化 + 风险熵项修正测试"""
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

from app.core.algorithms import PixelateDesensitizer, GaussianDesensitizer, IrreversibleDesensitizer
from app.services.anti_restore_service import AntiRestoreService


def _text_image():
    img = np.full((100, 220, 3), 245, np.uint8)
    cv2.putText(img, "TEST TEXT", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2)
    return img


def test_small_region_adaptive_destruction():
    """小区域自适应粒度：三种算法脱敏后与原图 SSIM 低（结构被重度破坏）。"""
    img = _text_image()
    region = {"x": 15, "y": 35, "w": 110, "h": 30}
    orig_gray = cv2.cvtColor(img[35:65, 15:125], cv2.COLOR_BGR2GRAY)
    for name, des in [
        ("像素化", PixelateDesensitizer()),
        ("高斯", GaussianDesensitizer()),
        ("不可逆", IrreversibleDesensitizer()),
    ]:
        proc = des.apply(img.copy(), region)
        proc_gray = cv2.cvtColor(proc[35:65, 15:125], cv2.COLOR_BGR2GRAY)
        s = ssim(orig_gray, proc_gray, data_range=255)
        assert s < 0.4, f"{name} 应重度破坏结构, SSIM={s:.2f}"


def test_risk_entropy_fixed():
    """熵项反转：均匀(低熵)=脱敏彻底→安全；余留结构(高熵)→更危险。"""
    uniform = AntiRestoreService._calc_risk_score(ssim_val=0.1, psnr_val=8.0, entropy=1.0)
    textured = AntiRestoreService._calc_risk_score(ssim_val=0.1, psnr_val=8.0, entropy=6.0)
    assert uniform < textured
    assert uniform < 30  # 均匀区域判安全


def test_risk_high_ssim_still_danger():
    """SSIM 高(没脱敏)仍是危险——熵项修正不影响弱脱敏的检出。"""
    high = AntiRestoreService._calc_risk_score(ssim_val=0.85, psnr_val=35.0, entropy=5.0)
    assert high >= 60  # danger
