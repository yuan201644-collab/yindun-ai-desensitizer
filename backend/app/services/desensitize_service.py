"""
================================================================
「隐盾」脱敏调度服务
================================================================
根据前端传来的脱敏请求，调度对应算法处理图片。
"""

import cv2
import numpy as np
from typing import Optional
from app.core.algorithms import DesensitizerRegistry, char_masker
from app.core.config import DesensitizeConfig


class DesensitizeService:
    """
    脱敏调度中心。
    支持：
    - 单区域/多区域批量处理
    - 混合模式（不同区域不同算法）
    - 纯文本脱敏
    """

    @staticmethod
    def process_image(
        image: np.ndarray,
        regions: list[dict],
        method: str = "pixelate",
        **kwargs
    ) -> np.ndarray:
        """
        对图片的多个区域应用脱敏算法。

        Args:
            image: BGR numpy 数组
            regions: [
                {"rect": {"x": int, "y": int, "w": int, "h": int}, "method": str, ...},
                ...
            ]
            method: 默认脱敏算法 (当 region 未指定 method 时使用)
        Returns:
            脱敏后的完整图片
        """
        result = image.copy()
        for region in regions:
            rect = region.get("rect", region)
            algo_name = region.get("method", method)

            try:
                desensitizer_class = DesensitizerRegistry.get(algo_name)
                desensitizer = desensitizer_class()
                result = desensitizer.apply(result, rect, **kwargs)
            except ValueError:
                print(f"[脱敏] 未知算法 {algo_name}，跳过区域 {rect}")
                continue

        return result

    @staticmethod
    def process_text(text: str, sensitive_spans: list[dict]) -> str:
        """
        对文本中的敏感片段进行掩码。
        Args:
            text: 原始文本
            sensitive_spans: [{"start": int, "end": int, "type": str}, ...]
        Returns:
            脱敏后的文本
        """
        result = list(text)
        for span in sensitive_spans:
            start, end = span["start"], span["end"]
            s_type = span.get("type", "default")
            masked = char_masker.mask(text[start:end], s_type)
            for i, ch in enumerate(masked):
                if start + i < len(result):
                    result[start + i] = ch
        return "".join(result)

    @staticmethod
    def detect_and_mask_text(text: str) -> tuple[str, list[dict]]:
        """
        自动检测文本中的敏感信息并掩码。
        返回: (脱敏后文本, 检测到的敏感片段列表)
        """
        from app.core.config import SENSITIVE_PATTERNS
        import re

        spans = []
        masked_text = text

        for type_name, config in SENSITIVE_PATTERNS.items():
            for match in re.finditer(config["pattern"], text):
                # 避免重叠
                if any(s["start"] <= match.start() < s["end"] or
                       s["start"] < match.end() <= s["end"]
                       for s in spans):
                    continue
                spans.append({
                    "start": match.start(),
                    "end": match.end(),
                    "type": type_name,
                    "category": config["category"],
                    "risk_level": config["risk_level"],
                    "matched_text": match.group(),
                })

        # 按位置排序
        spans.sort(key=lambda s: s["start"])
        # 应用掩码
        for span in reversed(spans):  # 从后往前处理，避免位置偏移
            s_type = span["type"]
            masked = char_masker.mask(span["matched_text"], s_type)
            masked_text = masked_text[:span["start"]] + masked + masked_text[span["end"]:]

        return masked_text, spans
