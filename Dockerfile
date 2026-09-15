# inklimner —— 位图转 SVG 线稿（激光切割用）
# 用法：
#   docker build -t inklimner .
#   docker run --rm -v "$PWD:/work" inklimner /work/input.png -o /work/output.svg
FROM python:3.12-slim

LABEL org.opencontainers.image.title="InkLimner" \
      org.opencontainers.image.description="Raster → SVG line art for laser cutting" \
      org.opencontainers.image.licenses="MIT"

# potrace：shape / multi 模式的圆滑轮廓（可选，装了更圆滑）
RUN apt-get update \
 && apt-get install -y --no-install-recommends potrace \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# headless 版 OpenCV，免装 libGL，镜像更小
RUN pip install --no-cache-dir opencv-python-headless numpy

COPY inklimner.py /app/inklimner.py

WORKDIR /work
ENTRYPOINT ["python", "/app/inklimner.py"]
