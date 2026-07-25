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
            self._model = YOLO(DetectionConfig.MODEL_NAME)
            self._available = True
            print("[Detection] YOLOv8-nano (CPU) 初始化完成")
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
        sensitive_labels = {"person", "cell phone", "book"}
        return [d for d in detections if d["label"] in sensitive_labels]
