# syntax=docker/dockerfile:1
# Serving image for Kaggle/AWS. Phase 0 builds this to prove the container path.
# Laptop GPU debugging can also use bare-metal Python; the image is for deploy.

FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-bench.txt ./
RUN pip3 install --upgrade pip \
    && pip3 install -r requirements.txt \
    && pip3 install -r requirements-bench.txt

COPY serving ./serving
COPY bench ./bench
COPY workload ./workload
COPY serving/models.yaml ./serving/models.yaml

EXPOSE 8000

# Default: rung 1 vLLM. Override with --rung / command.
CMD ["python3", "-m", "serving.vllm_server", "--rung", "1", "--host", "0.0.0.0", "--port", "8000"]
