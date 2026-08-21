"""
[隐盾] 目标检测服务 — YOLOv8-nano 封装 (CPU)
"""

import re
import numpy as np
from typing import Optional
from app.core.config import DetectionConfig


class DetectionService:
    _instance: Optional["DetectionService"] = None
    _model = None
    _available = None  # None=未检测, True=可用, False=不可用

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _init_model(self):
        if self._available is not None:
            return
        try:
            from ultralytics import YOLO
            import os
            custom = DetectionConfig.CUSTOM_MODEL_PATH
            if os.path.exists(custom):
                self._model = YOLO(custom)
                self._available = True
                print(f"[Detection] 自定义模型加载完成: {custom}")
            else:
                self._model = YOLO(DetectionConfig.MODEL_NAME)
                self._available = True
                print("[Detection] YOLOv8-nano (COCO 回退) 初始化完成")
        except Exception as e:
            self._available = False
            print(f"[Detection] YOLO 不可用 (重启系统后重试): {e}")

    def detect(self, image: np.ndarray) -> list[dict]:
        if self._available is None:
            self._init_model()
        if not self._available or self._model is None:
            return []

        results = self._model(
            image,
            conf=DetectionConfig.CONF_THRESHOLD,
            iou=DetectionConfig.IOU_THRESHOLD,
            verbose=False,
        )

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = result.names.get(cls_id, f"class_{cls_id}")
                detections.append({
                    "label": label,
                    "confidence": round(conf, 4),
                    "rect": {"x": int(x1), "y": int(y1), "w": int(x2-x1), "h": int(y2-y1)},
                })
        return detections

    @staticmethod
    def filter_sensitive(detections: list[dict]) -> list[dict]:
        sensitive_labels = set(DetectionConfig.SENSITIVE_CLASSES)
        return [d for d in detections if d["label"] in sensitive_labels]

    @staticmethod
    def _has_bankcard_cardno(obj: dict, text_regions: list[dict]) -> bool:
        """bank_card 框内是否识别到银联卡号(62 开头 ~14-19 位)。

        ⭐ 真银行卡框内必有 62xx 卡号；误检（执照/名片/印刷品等浅色卡状物）通常
        无卡号 → 判误检丢弃。注册号/税号等 51/91… 开头，不会误判成卡号。
        """
        r = obj.get("rect")
        if not r:
            return False
        for t in text_regions:
            tr = t.get("rect")
            if not tr:
                continue
            inside = (
                r["x"] <= tr["x"] + tr["w"] / 2 <= r["x"] + r["w"]
                and r["y"] <= tr["y"] + tr["h"] / 2 <= r["y"] + r["h"]
            )
            if not inside:
                continue
            # 去空格分段再匹配（OCR 常把 6222 0212 … 断开）
            text = "".join(t.get("text", "").split())
            if re.search(r"62\d{12,17}", text):
                return True
        return False

    @staticmethod
    def filter_by_ocr(object_regions: list[dict], text_regions: list[dict], img_w: int, img_h: int) -> list[dict]:
        """OCR 融合过滤：拦截目标检测的常见误检。

        ① 证件类对象框若几乎覆盖整图且内部大量文本行 → 误检丢弃。
           场景：聊天/文档截图被 YOLO 误判为证件（实测 id_card conf=0.78、
           框占图 90%、框内 14 行 OCR 文本）；真证件框面积占比小、内部文本
           少且结构化（身份证 ~7 行、银行卡 3-4 行）。
        ② bank_card 框内无银联卡号 → 误检丢弃（治"莫名报银行卡"）。
        """
        out = []
        for obj in object_regions:
            r = obj.get("rect")
            if not r or r["w"] <= 0 or r["h"] <= 0:
                continue
            area_ratio = (r["w"] * r["h"]) / max(1, img_w * img_h)
            # ⭐ 中心点在框内计数（宽松判定：聊天截图文本常部分超出误检框右边界，完全包含会漏计数）
            inside = sum(
                1 for t in text_regions
                if t.get("rect")
                and r["x"] <= t["rect"]["x"] + t["rect"]["w"] / 2 <= r["x"] + r["w"]
                and r["y"] <= t["rect"]["y"] + t["rect"]["h"] / 2 <= r["y"] + r["h"]
            )
            # 误检特征（聊天/文档截图被 YOLO 整体当证件，实测两张聊天截图框占 66%~90%）：
            #   ① 框占图 >60% —— 无论内部文本多少（第二张聊天截图框内文本在框外右侧）
            #   ② 框占 50-60% 且内部 >=5 行文本（配合中心点计数）
            # 真证件框通常 <50%（测试图 ~11%），不受影响
            if area_ratio > 0.6 or (area_ratio > 0.5 and inside >= 5):
                print(f"[Detection] 过滤误检 {obj.get('label')} conf={obj.get('confidence')} 面积占比={area_ratio:.2f} 内部文本={inside}行")
                continue
            # ⭐ 银行卡 OCR 融合复查：真卡框内必有 62xx 卡号，无卡号判误检
            if obj.get("label") == "bank_card" and not DetectionService._has_bankcard_cardno(obj, text_regions):
                r0 = obj.get("rect") or {}
                print(f"[Detection] 过滤误检 bank_card conf={obj.get('confidence')} 框内无银联卡号 rect={r0}")
                continue
            out.append(obj)
        return out
