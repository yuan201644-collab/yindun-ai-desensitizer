"""
================================================================
训练自定义检测模型（合成数据集 POC）
================================================================
用法: python scripts/train_custom.py
前置: CUDA torch（torch.cuda.is_available()==True）
输出: backend/models/yolo_custom.pt（*.pt 已 gitignore，不提交）
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from ultralytics import YOLO  # noqa: E402

DATA = ROOT / "datasets" / "synthetic" / "data.yaml"
OUT_MODEL = ROOT / "models" / "yolo_custom.pt"
EPOCHS = 50
IMGSZ = 320
BATCH = 16


def main():
    import torch
    if not torch.cuda.is_available():
        print("⚠️ CUDA 不可用，将用 CPU 训练（很慢）。建议先装 CUDA torch。")
        device = "cpu"
    else:
        device = 0
        print(f"✅ 使用 GPU: {torch.cuda.get_device_name(0)}")

    (ROOT / "models").mkdir(parents=True, exist_ok=True)
    model = YOLO("yolov8n.pt")
    model.train(
        data=str(DATA),
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        device=device,
        project=str(ROOT / "runs"),
        name="yolo_custom",
        exist_ok=True,
    )

    best = ROOT / "runs" / "yolo_custom" / "weights" / "best.pt"
    if best.exists():
        shutil.copy(best, OUT_MODEL)
        print(f"✅ 模型已保存: {OUT_MODEL}")
    else:
        print("⚠️ 未找到 best.pt，请检查训练输出")


if __name__ == "__main__":
    main()
