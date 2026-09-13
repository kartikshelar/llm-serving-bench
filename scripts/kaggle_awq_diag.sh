#!/usr/bin/env bash
# AWQ diagnostic protocol for one Kaggle T4 session.
# Does NOT replace Phase 2 ladder rows — appends diagnostic rows with notes.
#
# Usage (on Kaggle, GPU on, repo at /kaggle/working/llm-serving-bench):
#   bash scripts/kaggle_awq_diag.sh
#
# Protocol:
#   1) Inspect AWQ kernel modules (no tok/s claim)
#   2) For each max_tokens in {64, 256, 1024}:
#        serve rung 1 (fp16) → sweep c=1, 3 repeats, --sample-gpu
#        serve rung 2 (AWQ)  → sweep c=1, 3 repeats, --sample-gpu
#   3) Copy results/benchmarks.csv off the instance when done
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
HW="${HARDWARE:-kaggle_t4_x1}"
CSV="${CSV:-$ROOT/results/benchmarks.csv}"
PORT="${PORT:-8000}"

FP16_MODEL="Qwen/Qwen2.5-3B-Instruct"
AWQ_MODEL="Qwen/Qwen2.5-3B-Instruct-AWQ"

echo "[diag] root=$ROOT hardware=$HW csv=$CSV"

python scripts/inspect_awq_kernels.py | tee results/awq_kernel_inspect.txt || true

serve_and_sweep() {
  local rung="$1"
  local model="$2"
  local max_tok="$3"
  local note="$4"

  echo "[diag] stop prior server if any"
  pkill -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
  pkill -f "serving.vllm_server" 2>/dev/null || true
  sleep 2

  echo "[diag] start rung=$rung model=$model max_tokens=$max_tok"
  python -m serving.vllm_server --rung "$rung" --host 127.0.0.1 --port "$PORT" &
  local spid=$!

  # Wait for health / models endpoint
  for i in $(seq 1 120); do
    if curl -sf "$BASE_URL/v1/models" >/dev/null 2>&1; then
      echo "[diag] server ready (${i}s)"
      break
    fi
    if ! kill -0 "$spid" 2>/dev/null; then
      echo "[diag] server exited early" >&2
      return 1
    fi
    sleep 5
  done

  python -m bench.sweep \
    --base-url "$BASE_URL" \
    --hardware "$HW" \
    --model "$model" \
    --rung "$rung" \
    --gpu-count 1 \
    --concurrencies 1 \
    --repeats 3 \
    --max-tokens "$max_tok" \
    --requests-per-run 10 \
    --sample-gpu \
    --csv "$CSV" \
    --notes "$note"

  kill "$spid" 2>/dev/null || true
  wait "$spid" 2>/dev/null || true
  sleep 3
}

for MAX_TOK in 64 256 1024; do
  serve_and_sweep 1 "$FP16_MODEL" "$MAX_TOK" \
    "AWQ_DIAG fp16 c=1 max_tokens=${MAX_TOK}; sample_gpu; compare vs AWQ short/long decode"
  serve_and_sweep 2 "$AWQ_MODEL" "$MAX_TOK" \
    "AWQ_DIAG awq c=1 max_tokens=${MAX_TOK}; sample_gpu; dequant-amortization hypothesis"
done

echo "[diag] done. New rows tagged AWQ_DIAG in $CSV"
echo "[diag] Also see results/awq_kernel_inspect.txt"
