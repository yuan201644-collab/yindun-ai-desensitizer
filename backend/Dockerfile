# ============================================
# 「隐盾」后端 GPU 环境 Docker 镜像
# 基于 NVIDIA CUDA 基础镜像
# 构建: docker build -t yindun-backend:gpu .
# 运行: docker run --gpus all -p 8000:8000 yindun-backend:gpu
# ============================================

FROM nvidia/cuda:11.8-cudnn8-runtime-ubuntu22.04

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 应用代码
COPY app/ ./app/

# 预下载 PaddleOCR 模型 (可选，加快首次启动)
# RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='ch', use_gpu=True)"

EXPOSE 8000

# 内存处理，不需要持久化卷
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
