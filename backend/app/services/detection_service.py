"""
[隐盾] 目标检测服务 — YOLOv8-nano 封装 (CPU)
"""

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
    def filter_by_ocr(object_regions: list[dict], text_regions: list[dict], img_w: int, img_h: int) -> list[dict]:
        """OCR 融合过滤：证件类对象框若几乎覆盖整图且内部大量文本行 → 误检丢弃。

        场景：聊天/文档截图被 YOLO 误判为证件（实测 id_card conf=0.78、
        框占图 90%、框内 14 行 OCR 文本）；真证件框面积占比小、内部文本
        少且结构化（身份证 ~7 行、银行卡 3-4 行）。
        """
        out = []
        for obj in object_regions:
            r = obj.get("rect")
            if not r or r["w"] <= 0 or r["h"] <= 0:
                continue
            area_ratio = (r["w"] * r["h"]) / max(1, img_w * img_h)
            inside = sum(
                1 for t in text_regions
                if t.get("rect")
                and t["rect"]["x"] >= r["x"] and t["rect"]["y"] >= r["y"]
                and t["rect"]["x"] + t["rect"]["w"] <= r["x"] + r["w"]
                and t["rect"]["y"] + t["rect"]["h"] <= r["y"] + r["h"]
            )
            # 误检特征：框占图 >80% 且内部 >=5 行文本（证件不会整图+满文字）
            if area_ratio > 0.8 and inside >= 5:
                print(f"[Detection] 过滤误检 {obj.get('label')} conf={obj.get('confidence')} 面积占比={area_ratio:.2f} 内部文本={inside}行")
                continue
            out.append(obj)
        return out
