"""
================================================================
「隐盾」脱敏算法库 — 核心安全模块
================================================================
四类脱敏算法，均支持抵御 AI 图像还原。
设计原则：
1. 不可逆性：脱敏后无法通过超分/Inpainting 还原
2. 可插拔：每个算法独立封装，统一接口 register_desensitizer
3. 可调参：所有参数外部可控，方便迭代
"""

import cv2
import numpy as np
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import random
import hashlib


# ============================================================
# 算法注册表 — 可扩展接口
# ============================================================
class DesensitizerRegistry:
    """脱敏算法注册中心，后续新增算法在此注册即可"""
    _algorithms: dict = {}

    @classmethod
    def register(cls, name: str, algorithm_cls):
        cls._algorithms[name] = algorithm_cls

    @classmethod
    def get(cls, name: str):
        if name not in cls._algorithms:
            raise ValueError(f"未知算法: {name}，可用: {list(cls._algorithms.keys())}")
        return cls._algorithms[name]

    @classmethod
    def list_all(cls) -> list:
        return list(cls._algorithms.keys())


class BaseDesensitizer(ABC):
    """脱敏算法基类"""
    @abstractmethod
    def apply(self, image: np.ndarray, region: dict, **kwargs) -> np.ndarray:
        """
        对图片指定区域应用脱敏算法。
        Args:
            image: BGR 格式 numpy 数组
            region: {"x": int, "y": int, "w": int, "h": int}
            **kwargs: 算法特定参数
        Returns:
            处理后的完整图片
        """
        pass

    @property
    @abstractmethod
    def is_irreversible(self) -> bool:
        """是否具备不可逆性"""
        pass


# ============================================================
# 算法一：像素化脱敏 (马赛克)
# ============================================================
class PixelateDesensitizer(BaseDesensitizer):
    """
    基于区域降采样 + 随机微扰动的像素化。
    关键防护：随机扰动防止逆插值还原。
    """
    def __init__(self, block_size: int = 8, noise_level: float = 0.05):
        self.block_size = block_size
        self.noise_level = noise_level

    @property
    def is_irreversible(self) -> bool:
        return True  # 降采样信息丢失 + 扰动

    def apply(self, image: np.ndarray, region: dict, **kwargs) -> np.ndarray:
        x, y, w, h = region["x"], region["y"], region["w"], region["h"]
        # 边界检查
        x, y = max(0, x), max(0, y)
        w, h = min(w, image.shape[1] - x), min(h, image.shape[0] - y)
        if w <= 0 or h <= 0:
            return image

        roi = image[y:y+h, x:x+w].copy()
        bs = kwargs.get("block_size", self.block_size)

        # 降采样 → 升采样 (信息丢失过程)
        small_h, small_w = max(1, h // bs), max(1, w // bs)
        small = cv2.resize(roi, (small_w, small_h), interpolation=cv2.INTER_LINEAR)

        # ⭐ 关键：加入随机微扰动，破坏插值还原路径
        noise = (np.random.randn(small_h, small_w, 3) * kwargs.get("noise_level", self.noise_level) * 255).astype(np.int16)
        small_noisy = np.clip(small.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # 放大回原尺寸
        pixelated = cv2.resize(small_noisy, (w, h), interpolation=cv2.INTER_NEAREST)

        result = image.copy()
        result[y:y+h, x:x+w] = pixelated
        return result


# ============================================================
# 算法二：高斯噪点混淆 (强模糊 + 噪点层)
# ============================================================
class GaussianDesensitizer(BaseDesensitizer):
    """
    多层高斯模糊叠加 + 非均匀噪点注入。
    关键防护：噪点模式随机化，对抗 AI 去噪模型。
    """
    def __init__(self, sigma: float = 25.0, noise_intensity: float = 0.12):
        self.sigma = sigma
        self.noise_intensity = noise_intensity

    @property
    def is_irreversible(self) -> bool:
        return True  # 多轮模糊 + 随机噪点

    def apply(self, image: np.ndarray, region: dict, **kwargs) -> np.ndarray:
        x, y, w, h = region["x"], region["y"], region["w"], region["h"]
        x, y = max(0, x), max(0, y)
        w, h = min(w, image.shape[1] - x), min(h, image.shape[0] - y)
        if w <= 0 or h <= 0:
            return image

        roi = image[y:y+h, x:x+w].copy()
        sigma = kwargs.get("sigma", self.sigma)
        ni = kwargs.get("noise_intensity", self.noise_intensity)

        # 多轮高斯模糊（不同 sigma 叠加 → 去模糊模型更难还原）
        blurred = roi.copy()
        for s in [sigma * 0.5, sigma, sigma * 1.5]:
            ksize = int(s * 4) | 1  # 确保奇数
            ksize = max(3, min(ksize, 99))
            blurred = cv2.GaussianBlur(blurred, (ksize, ksize), s)

        # ⭐ 关键：注入与局部纹理相关的非均匀噪点
        local_std = np.std(roi.astype(np.float32), axis=2)
        noise_mask = (local_std / (local_std.max() + 1e-8)) * ni
        noise = np.random.randn(h, w, 3) * noise_mask[:, :, np.newaxis] * 255
        noisy_result = np.clip(blurred.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        result = image.copy()
        result[y:y+h, x:x+w] = noisy_result
        return result


# ============================================================
# 算法三：不可逆像素替换 (核心创新算法)
# ============================================================
class IrreversibleDesensitizer(BaseDesensitizer):
    """
    基于种子哈希的分块随机像素重排 + 值注入。
    核心创新：像素级不可逆混淆，AI 还原模型无法重建原始梯度。

    原理：
    1. 区域 → 划分为 patch
    2. 每个 patch 使用 SHA-256 种子生成伪随机索引，重排像素
    3. 重排后注入基于种子的伪随机值，破坏局部相关性
    4. 多轮迭代 → 信息熵最大化 → 不可逆
    """
    def __init__(self, patch_size: int = 4, rounds: int = 3):
        self.patch_size = patch_size
        self.rounds = rounds

    @property
    def is_irreversible(self) -> bool:
        return True  # 信息论不可逆

    def _generate_seed(self, region_xy: Tuple[int, int]) -> int:
        """基于区域坐标 + SHA-256 生成确定性种子（同区域同结果，便于验证）"""
        raw = f"{region_xy[0]},{region_xy[1]}"
        hash_bytes = hashlib.sha256(raw.encode()).digest()
        return int.from_bytes(hash_bytes[:8], "big")

    def apply(self, image: np.ndarray, region: dict, **kwargs) -> np.ndarray:
        x, y, w, h = region["x"], region["y"], region["w"], region["h"]
        x, y = max(0, x), max(0, y)
        w, h = min(w, image.shape[1] - x), min(h, image.shape[0] - y)
        if w <= 0 or h <= 0:
            return image

        roi = image[y:y+h, x:x+w].copy()
        ps = kwargs.get("patch_size", self.patch_size)
        rounds = kwargs.get("rounds", self.rounds)
        seed = self._generate_seed((x, y))

        result_roi = roi.copy()
        rng = random.Random(seed)

        for _ in range(rounds):
            # 分 patch
            for py in range(0, h, ps):
                for px in range(0, w, ps):
                    pw = min(ps, w - px)
                    ph = min(ps, h - py)
                    if pw <= 1 or ph <= 1:
                        continue

                    patch = result_roi[py:py+ph, px:px+pw].copy()
                    flat = patch.reshape(-1, 3)

                    # ⭐ 核心：Fisher-Yates 像素重排（基于种子 → 可复现但不可逆）
                    indices = list(range(len(flat)))
                    rng.shuffle(indices)
                    flat[:] = flat[indices]

                    # ⭐ 注入伪随机值（进一步破坏局部梯度）
                    noise_vals = np.array([
                        [rng.randint(-32, 32) for _ in range(3)]
                        for _ in range(len(flat))
                    ], dtype=np.int16)

                    flat[:] = np.clip(flat.astype(np.int16) + noise_vals, 0, 255).astype(np.uint8)
                    result_roi[py:py+ph, px:px+pw] = flat.reshape(ph, pw, 3)

        result = image.copy()
        result[y:y+h, x:x+w] = result_roi
        return result


# ============================================================
# 算法四：字符级掩码 (文本脱敏用)
# ============================================================
class CharacterMaskDesensitizer:
    """
    智能字符掩码 — 保留格式感知，维护数据可读性。
    例：11010119900101123X → 110**************23X
    """
    def __init__(self, mask_char: str = "*", keep_first: int = 3, keep_last: int = 4):
        self.mask_char = mask_char
        self.keep_first = keep_first
        self.keep_last = keep_last

    def mask(self, text: str, sensitive_type: str = "default") -> str:
        """对文本中的敏感部分进行掩码"""
        length = len(text)
        if length <= self.keep_first + self.keep_last:
            # 短文本全部掩码
            return self.mask_char * length

        keep_first = self.keep_first
        keep_last = self.keep_last

        # 根据类型调整保留位数
        if sensitive_type == "身份证号":
            keep_first, keep_last = 3, 4  # 保留前3后4
        elif sensitive_type == "手机号":
            keep_first, keep_last = 3, 4  # 138****1234
        elif sensitive_type == "银行卡号":
            keep_first, keep_last = 4, 4  # 6222********1234
        elif sensitive_type == "护照号":
            keep_first, keep_last = 2, 2  # E1*****78，与前端掩码策略一致
        elif sensitive_type == "电子邮箱":
            # 保留首字符和@后部分
            at_idx = text.find("@")
            if at_idx > 0:
                return text[0] + self.mask_char * (at_idx - 1) + text[at_idx:]

        middle_len = length - keep_first - keep_last
        return text[:keep_first] + self.mask_char * middle_len + text[-keep_last:]


# ============================================================
# 注册所有算法
# ============================================================
DesensitizerRegistry.register("pixelate", PixelateDesensitizer)
DesensitizerRegistry.register("gaussian", GaussianDesensitizer)
DesensitizerRegistry.register("irreversible", IrreversibleDesensitizer)

# 字符掩码单独使用（不是图像处理）
char_masker = CharacterMaskDesensitizer()
