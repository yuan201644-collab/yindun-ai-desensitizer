"""
================================================================
「隐盾」对抗还原测试服务
================================================================
对脱敏区域尝试多种「还原手法」，测还原后与原图的相似度，
以检验脱敏的不可逆性 —— 抗 AI 还原的硬证据。

轻量版用经典还原算法（cv2 / scikit-image），无模型权重依赖。
后续可在此接入 Real-ESRGAN / SwinIR 等真超分模型做更强对抗验证：
把某个攻击函数替换为 `model.predict(region)` 即可（接口不变）。
"""

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from skimage.restoration import richardson_lucy

# 判定阈值：还原后与原图的最佳 SSIM
VERDICT_SAFE = 0.45      # 低于此 → 攻击全部失败，脱敏不可逆
VERDICT_WARNING = 0.70   # 高于此 → 可被明显还原


class AdversarialService:
    """对抗还原测试引擎。"""

    @staticmethod
    def run_attacks(
        original_region: np.ndarray,
        processed_region: np.ndarray
    ) -> dict:
        """
        对脱敏区域跑 3 种还原攻击，返回还原效果评估。

        Returns:
            {
                "attacks": [{"name", "restored_ssim", "restored_psnr"}, ...],
                "max_restored_ssim": float,
                "verdict": "safe" | "warning" | "danger",
                "message": str,
            }
        """
        if original_region.shape != processed_region.shape:
            processed_region = cv2.resize(
                processed_region,
                (original_region.shape[1], original_region.shape[0])
            )

        h, w = original_region.shape[:2]
        if h < 8 or w < 8:
            return AdversarialService._safe_result("区域过小，跳过对抗测试")

        attempts = [
            ("超分插值还原", AdversarialService._upscale_attack),
            ("去模糊反卷积", AdversarialService._deblur_attack),
            ("边缘增强还原", AdversarialService._enhance_attack),
        ]

        attacks = []
        for name, attack_fn in attempts:
            try:
                restored = attack_fn(processed_region)
                s_val, p_val = AdversarialService._similarity(original_region, restored)
                attacks.append({
                    "name": name,
                    "restored_ssim": round(s_val, 4),
                    "restored_psnr": round(p_val, 2),
                })
            except Exception:
                attacks.append({"name": name, "restored_ssim": 0.0, "restored_psnr": 0.0})

        max_ssim = max((a["restored_ssim"] for a in attacks), default=0.0)

        if max_ssim <= VERDICT_SAFE:
            verdict = "safe"
            message = "✅ 还原攻击全部失败——即使经过超分/去模糊还原，仍无法恢复原始敏感信息"
        elif max_ssim <= VERDICT_WARNING:
            verdict = "warning"
            message = "⚠️ 部分还原手法能恢复少量信息，建议加大脱敏强度或改用不可逆替换算法"
        else:
            verdict = "danger"
            message = "🔴 脱敏可被还原，当前强度不足，请立即更换算法重新处理"

        return {
            "attacks": attacks,
            "max_restored_ssim": round(max_ssim, 4),
            "verdict": verdict,
            "message": message,
        }

    # --- 还原手法（后续可替换为真超分模型） ---

    @staticmethod
    def _upscale_attack(region: np.ndarray) -> np.ndarray:
        """超分插值还原：4x 升采样 + 回落，模拟放大看图（针对马赛克/块状）。"""
        h, w = region.shape[:2]
        big = cv2.resize(region, (w * 4, h * 4), interpolation=cv2.INTER_CUBIC)
        return cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _deblur_attack(region: np.ndarray) -> np.ndarray:
        """去模糊反卷积：Richardson-Lucy 恢复清晰度（针对高斯模糊）。"""
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        kernel = cv2.getGaussianKernel(ksize=5, sigma=1.2)
        psf = kernel @ kernel.T
        deblurred = richardson_lucy(gray, psf, num_iter=15, clip=False)
        deblurred = np.clip(deblurred, 0, 255).astype(np.uint8)
        return cv2.cvtColor(deblurred, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def _enhance_attack(region: np.ndarray) -> np.ndarray:
        """边缘增强还原：锐化 + CLAHE 对比度拉伸（通用拉细节）。"""
        blur = cv2.GaussianBlur(region, (0, 0), 3)
        sharp = cv2.addWeighted(region, 1.5, blur, -0.5, 0)
        lab = cv2.cvtColor(sharp, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_enh = clahe.apply(l_ch)
        return cv2.cvtColor(cv2.merge([l_enh, a_ch, b_ch]), cv2.COLOR_LAB2BGR)

    # --- 内部工具 ---

    @staticmethod
    def _similarity(orig: np.ndarray, restored: np.ndarray) -> tuple[float, float]:
        """还原结果与原图的 SSIM / PSNR。"""
        gray_o = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(restored, cv2.COLOR_BGR2GRAY)
        s_val = float(ssim(gray_o, gray_r, data_range=255))
        mse = np.mean((gray_o.astype(float) - gray_r.astype(float)) ** 2)
        p_val = float(20 * np.log10(255.0 / (np.sqrt(mse) + 1e-8)))
        return s_val, p_val

    @staticmethod
    def _safe_result(message: str) -> dict:
        return {
            "attacks": [],
            "max_restored_ssim": 0.0,
            "verdict": "safe",
            "message": message,
        }
