"""强度检测可视化报告（4 维雷达）测试"""
import cv2
import numpy as np

from app.services.anti_restore_service import AntiRestoreService


def test_build_report_dimensions_in_range():
    """4 维数值都在 0-100，labels 齐全。"""
    r = AntiRestoreService._build_report(ssim_val=0.1, psnr_val=20, entropy=6.0, adv_verdict="safe")
    d = r["dimensions"]
    assert set(d.keys()) == {"privacy", "usability", "texture", "noise_control"}
    for v in d.values():
        assert 0 <= v <= 100
    assert set(r["labels"].keys()) == set(d.keys())


def test_privacy_higher_when_adversarial_safe():
    """对抗判定 safe → 隐私防护更高。"""
    safe = AntiRestoreService._build_report(ssim_val=0.1, psnr_val=20, entropy=6.0, adv_verdict="safe")
    unsafe = AntiRestoreService._build_report(ssim_val=0.1, psnr_val=20, entropy=6.0, adv_verdict="warning")
    assert safe["dimensions"]["privacy"] > unsafe["dimensions"]["privacy"]


def test_privacy_higher_when_ssim_lower():
    """SSIM 越低（结构破坏越彻底）→ 隐私防护越高。"""
    low = AntiRestoreService._build_report(ssim_val=0.05, psnr_val=20, entropy=6.0, adv_verdict="safe")
    high = AntiRestoreService._build_report(ssim_val=0.8, psnr_val=20, entropy=6.0, adv_verdict="safe")
    assert low["dimensions"]["privacy"] > high["dimensions"]["privacy"]


def test_check_region_includes_report():
    """check_region 返回带 report（4 维）。"""
    img = np.full((50, 50, 3), 240, np.uint8)
    cv2.putText(img, "AB", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 40, 40), 2)
    proc = img.copy()
    proc[10:40, 5:40] = 128  # 模拟脱敏
    res = AntiRestoreService.check_region(img, proc)
    assert "report" in res
    assert "dimensions" in res["report"]
    assert "noise_control" in res["report"]["dimensions"]
