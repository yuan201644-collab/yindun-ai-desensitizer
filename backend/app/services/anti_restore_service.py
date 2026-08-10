"""
================================================================
「隐盾」反还原检测服务
================================================================
对脱敏后的图片进行安全性评估，检测 AI 还原风险。

评估维度：
1. 结构相似度 (SSIM) — 与原始脱敏区域对比
2. 峰值信噪比 (PSNR)
3. 局部纹理熵 — 检测信息残留
4. 综合风险评分

⚠️ 当前版本为轻量级近似评估，后续可接入超分模型做对抗性验证。
"""

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from app.core.config import AntiRestoreConfig
from app.services.adversarial_service import AdversarialService


class AntiRestoreService:
    """
    脱敏强度检测引擎。
    通过数学度量评估脱敏区域的不可逆程度。
    """

    @staticmethod
    def check_region(
        original_region: np.ndarray,
        processed_region: np.ndarray
    ) -> dict:
        """
        对单个脱敏区域进行风险评估。

        Returns:
            {
                "ssim": float,           # 结构相似度 (越低越安全)
                "psnr": float,           # 峰值信噪比 (越低越安全)
                "texture_entropy": float, # 纹理熵 (越高越安全=噪声多)
                "risk_score": int,       # 0-100 风险评分 (越低越安全)
                "risk_level": str,       # "safe" / "warning" / "danger"
                "suggestion": str,        # 加固建议
            }
        """
        # 统一尺寸
        if original_region.shape != processed_region.shape:
            processed_region = cv2.resize(
                processed_region,
                (original_region.shape[1], original_region.shape[0])
            )

        gray_orig = cv2.cvtColor(original_region, cv2.COLOR_BGR2GRAY)
        gray_proc = cv2.cvtColor(processed_region, cv2.COLOR_BGR2GRAY)

        h, w = gray_orig.shape
        if h < 7 or w < 7:
            return AntiRestoreService._safe_result("区域过小，无需检测")

        # 1. SSIM 计算
        try:
            ssim_val = float(ssim(gray_orig, gray_proc, data_range=255))
        except Exception:
            ssim_val = 0.0

        # 2. PSNR 计算
        mse = np.mean((gray_orig.astype(float) - gray_proc.astype(float)) ** 2)
        psnr_val = float(20 * np.log10(255.0 / np.sqrt(mse + 1e-8)))

        # 3. 局部纹理熵 — 衡量信息残留
        entropy = AntiRestoreService._compute_local_entropy(gray_proc)

        # 4. 综合风险评估
        # SSIM 高 → 结构保留多 → 可还原风险高
        # PSNR 高 → 像素差异小 → 可还原风险高
        # 熵高 → 仍有余留纹理/结构 → 可还原风险高（熵低=均匀=脱敏彻底 → 安全）
        risk_score = AntiRestoreService._calc_risk_score(ssim_val, psnr_val, entropy)

        # 5. 风险等级
        if risk_score < 30:
            risk_level = "safe"
            suggestion = "脱敏强度充足，可有效抵御 AI 还原"
        elif risk_score < 60:
            risk_level = "warning"
            suggestion = "存在中度还原风险，建议提高脱敏强度或更换算法（如不可逆替换）"
        else:
            risk_level = "danger"
            suggestion = "⚠️ 高还原风险！建议立即更换为不可逆脱敏算法，增大处理强度"

        # 6. 对抗还原测试 — 尝试还原手法，检验脱敏是否可逆
        adversarial = AdversarialService.run_attacks(original_region, processed_region)

        return {
            "ssim": round(ssim_val, 4),
            "psnr": round(psnr_val, 2),
            "texture_entropy": round(entropy, 4),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "suggestion": suggestion,
            "adversarial": adversarial,
        }

    @staticmethod
    def check_full_image(
        original: np.ndarray,
        processed: np.ndarray,
        regions: list[dict]
    ) -> dict:
        """
        对整张脱敏图片进行全局安全性评估。
        Args:
            original: 原始图片
            processed: 脱敏后图片
            regions: 脱敏区域列表
        Returns:
            总体评估 + 逐区域详情
        """
        region_results = []
        total_risk = 0

        for i, region in enumerate(regions):
            rect = region.get("rect", region)
            x, y = rect["x"], rect["y"]
            # 兼容不同 key 命名: w/width, h/height
            rw = rect.get("w") or rect.get("width") or 0
            rh = rect.get("h") or rect.get("height") or 0
            if rw <= 0 or rh <= 0:
                continue

            # 提取原始和处理后的区域
            orig_roi = original[y:y+rh, x:x+rw]
            proc_roi = processed[y:y+rh, x:x+rw]

            result = AntiRestoreService.check_region(orig_roi, proc_roi)
            result["region_index"] = i
            region_results.append(result)
            total_risk += result["risk_score"]

        avg_risk = int(total_risk / len(region_results)) if region_results else 0

        # 全局评估
        if avg_risk < 30:
            global_level = "safe"
            global_msg = "✅ 整体脱敏效果良好，可放心使用"
        elif avg_risk < 60:
            global_level = "warning"
            global_msg = "⚠️ 部分区域存在还原风险，建议加固"
        else:
            global_level = "danger"
            global_msg = "🔴 脱敏强度不足，请重新处理"

        # 对抗还原汇总：取各区域最坏判定
        verdicts = [r.get("adversarial", {}).get("verdict", "safe") for r in region_results]
        if "danger" in verdicts:
            adv_verdict = "danger"
            adv_msg = "🔴 存在可被还原的区域，请立即更换脱敏算法重新处理"
        elif "warning" in verdicts:
            adv_verdict = "warning"
            adv_msg = "⚠️ 部分区域可被部分还原，建议加固"
        else:
            adv_verdict = "safe"
            adv_msg = "✅ 还原攻击全部失败——即使经过超分/去模糊还原，仍无法恢复原始敏感信息"

        return {
            "global_risk_score": avg_risk,
            "global_risk_level": global_level,
            "global_message": global_msg,
            "region_details": region_results,
            "total_regions_checked": len(region_results),
            "adversarial_summary": {
                "verdict": adv_verdict,
                "message": adv_msg,
            },
        }

    # --- 内部方法 ---

    @staticmethod
    def _compute_local_entropy(gray: np.ndarray) -> float:
        """计算局部纹理熵"""
        ps = AntiRestoreConfig.TEXTURE_PATCH_SIZE
        h, w = gray.shape
        entropies = []
        for y in range(0, h - ps, ps):
            for x in range(0, w - ps, ps):
                patch = gray[y:y+ps, x:x+ps]
                hist = cv2.calcHist([patch], [0], None, [256], [0, 256])
                hist = hist / hist.sum()
                entropy = -np.sum(hist * np.log2(hist + 1e-8))
                entropies.append(entropy)
        return float(np.mean(entropies)) if entropies else 0.0

    @staticmethod
    def _calc_risk_score(ssim_val: float, psnr_val: float, entropy: float) -> int:
        """综合计算风险评分 0-100"""
        # SSIM 贡献：越高越危险
        ssim_risk = ssim_val * 100
        # PSNR 贡献：高于阈值说明保留太多信息
        psnr_risk = max(0, (psnr_val / 50.0) * 100)
        # 熵贡献：熵高(仍有余留纹理/结构) → 危险；熵低(均匀=脱敏彻底) → 安全
        entropy_risk = max(0, (entropy / 8.0) * 100)

        # 加权综合 (SSIM 权重最高 — 结构信息最关键)
        score = ssim_risk * 0.5 + psnr_risk * 0.25 + entropy_risk * 0.25
        return int(min(100, max(0, score)))

    @staticmethod
    def _safe_result(message: str) -> dict:
        return {
            "ssim": 0.0, "psnr": 0.0, "texture_entropy": 0.0,
            "risk_score": 0, "risk_level": "safe", "suggestion": message,
        }
