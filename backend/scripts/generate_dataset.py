"""
================================================================
合成数据集生成器 — 生成"证件/银行卡/快递单/发票"卡面矩形检测数据
================================================================
输出 YOLO 格式到 backend/datasets/synthetic/：
  images/*.jpg   标签 labels/*.txt   data.yaml
每张图：随机背景 + 1 个卡面矩形（带占位文字条）+ 随机位置/尺寸/明暗。

说明：POC 用合成数据，训练出的是"卡面矩形"检测器；
真实场景需真实标注数据 + GPU 再训（本脚本是数据链路模板）。
"""

import random
from pathlib import Path

import cv2
import numpy as np

CLASSES = ["id_card", "bank_card", "invoice", "express_slip"]
PER_CLASS = 50


def generate_one(idx: int, cls_id: int, img_dir: Path, lbl_dir: Path, size: int = 640):
    bg = np.random.randint(30, 220, (size, size, 3), dtype=np.uint8)
    noise = np.random.randint(0, 20, (size, size, 3), dtype=np.uint8)
    bg = np.clip(bg.astype(int) + noise, 0, 255).astype(np.uint8)

    cw = random.randint(int(size * 0.35), int(size * 0.7))
    ch = int(cw * random.uniform(0.55, 0.66))
    cx = random.randint(cw // 2 + 10, size - cw // 2 - 10)
    cy = random.randint(ch // 2 + 10, size - ch // 2 - 10)
    x1, y1 = cx - cw // 2, cy - ch // 2

    # 卡面（白底 + 标题条 + 占位文字条）
    card = np.full((ch, cw, 3), (245, 245, 245), dtype=np.uint8)
    cv2.rectangle(card, (0, 0), (cw, int(ch * 0.22)), (70, 70, 95), -1)
    for j in range(4):
        ty = int(ch * (0.32 + j * 0.15))
        cv2.rectangle(card, (int(cw * 0.08), ty), (int(cw * 0.92), ty + int(ch * 0.07)), (125, 125, 135), -1)
    # 类别差异化配色
    if cls_id == 0:   # id_card 偏蓝
        card[:, :, 0] = np.clip(card[:, :, 0].astype(int) + 25, 0, 255).astype(np.uint8)
    elif cls_id == 1: # bank_card 偏紫
        card[:, :, 2] = np.clip(card[:, :, 2].astype(int) + 30, 0, 255).astype(np.uint8)
    elif cls_id == 2: # invoice 偏黄
        card[:, :, 1] = np.clip(card[:, :, 1].astype(int) + 20, 0, 255).astype(np.uint8)
    else:             # express_slip 偏绿
        card[:, :, 1] = np.clip(card[:, :, 1].astype(int) + 40, 0, 255).astype(np.uint8)

    canvas = bg.copy()
    canvas[y1:y1 + ch, x1:x1 + cw] = card

    img_name = f"{cls_id}_{idx:04d}.jpg"
    # cv2.imwrite 在 Windows 处理不了中文路径 → 用 imencode + 字节写入
    ok, buf = cv2.imencode(".jpg", canvas)
    if ok:
        (img_dir / img_name).write_bytes(buf.tobytes())

    # YOLO 标签（归一化 cx cy w h）
    dw, dh = 1.0 / size, 1.0 / size
    ncx, ncy = (x1 + cw / 2) * dw, (y1 + ch / 2) * dh
    nw, nh = cw * dw, ch * dh
    (lbl_dir / (img_name.replace(".jpg", ".txt"))).write_text(
        f"{cls_id} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}\n"
    )


def main():
    root = Path(__file__).parent.parent / "datasets" / "synthetic"
    img_dir, lbl_dir = root / "images", root / "labels"
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    idx = 0
    for cls_id in range(len(CLASSES)):
        for _ in range(PER_CLASS):
            generate_one(idx, cls_id, img_dir, lbl_dir)
            idx += 1

    (root / "data.yaml").write_text(
        f"path: {root.as_posix()}\n"
        f"train: images\nval: images\n"
        f"nc: {len(CLASSES)}\n"
        f"names: {CLASSES}\n",
        encoding="utf-8",
    )
    print(f"OK, generated {idx} images -> {root}")


if __name__ == "__main__":
    main()
