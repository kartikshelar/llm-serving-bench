#!/bin/bash
# Fast serve bootstrap on DLAMI. Usage: ./aws_serve.sh <rung>
# rung 1|3 use vLLM docker; rung 0 uses HF in a pytorch container.
set -euo pipefail
RUNG="${1:?rung required}"
MODEL_FP16="Qwen/Qwen2.5-3B-Instruct"
MODEL_AWQ="Qwen/Qwen2.5-3B-Instruct-AWQ"
NAME="llm-serve"

sudo docker rm -f "$NAME" 2>/dev/null || true

case "$RUNG" in
  1)
    START=$(date +%s)
    sudo docker run -d --name "$NAME" --gpus all -p 8000:8000 \
      -v /home/ubuntu/.cache/huggingface:/root/.cache/huggingface \
      vllm/vllm-openai:v0.8.5 \
      --model "$MODEL_FP16" --dtype float16 --max-model-len 4096 \
      --gpu-memory-utilization 0.90 --host 0.0.0.0 --port 8000
    ;;
  3)
    START=$(date +%s)
    sudo docker run -d --name "$NAME" --gpus all -p 8000:8000 \
      -v /home/ubuntu/.cache/huggingface:/root/.cache/huggingface \
      vllm/vllm-openai:v0.8.5 \
      --model "$MODEL_FP16" --dtype float16 --max-model-len 4096 \
      --gpu-memory-utilization 0.90 --enable-prefix-caching \
      --host 0.0.0.0 --port 8000
    ;;
  2)
    START=$(date +%s)
    sudo docker run -d --name "$NAME" --gpus all -p 8000:8000 \
      -v /home/ubuntu/.cache/huggingface:/root/.cache/huggingface \
      vllm/vllm-openai:v0.8.5 \
      --model "$MODEL_AWQ" --quantization awq --dtype float16 \
      --max-model-len 4096 --gpu-memory-utilization 0.90 \
      --host 0.0.0.0 --port 8000
    ;;
  0)
    START=$(date +%s)
    # HF naive server from uploaded repo code
    sudo docker run -d --name "$NAME" --gpus all -p 8000:8000 \
      -v /home/ubuntu/llm-serving-bench:/app \
      -v /home/ubuntu/.cache/huggingface:/root/.cache/huggingface \
      -w /app \
      --entrypoint bash \
      vllm/vllm-openai:v0.8.5 \
      -lc 'pip install -q fastapi uvicorn pydantic pyyaml transformers accelerate && python3 -m serving.hf_server --rung 0 --host 0.0.0.0 --port 8000'
    ;;
  *)
    echo "bad rung"; exit 1
    ;;
esac

for i in $(seq 1 120); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null; then
    END=$(date +%s)
    echo "HEALTHY rung=$RUNG cold_start_container_sec=$((END-START))"
    exit 0
  fi
  sleep 5
  echo "wait_$i"
done
echo "HEALTH_TIMEOUT"
sudo docker logs "$NAME" 2>&1 | tail -50
exit 1
