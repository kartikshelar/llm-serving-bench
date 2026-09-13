# Findings

Per-rung analysis against pre-registered predictions in the README.

Every throughput figure is over **n=3** `errors=0` repeats from
`results/benchmarks.csv`. Tables report **mean, sample SD, min, max**.

Model locked: `Qwen/Qwen2.5-3B-Instruct` (rung 2: `…-AWQ`). Accuracy not measured.

---

## Predictions versus outcomes

| Rung | Prediction | Outcome |
|---|---|---|
| 0 HF naive | Slowest baseline | **Confirmed.** Flat ~20 tok/s on Kaggle T4, ~26 on `aws_g4dn.xlarge`; does not scale with concurrency (SD ≪ 1 tok/s). |
| 1 vLLM | Large gain vs 0 at concurrency ≥8 | **Confirmed.** Peak mean 508.9 (`kaggle_t4_x1`, c=32) vs ~20 HF; 472.0 on `aws_g4dn.xlarge`. |
| 2 AWQ INT4 | Moderate throughput / memory win | **Falsified on throughput.** Mean 440.6 vs 508.9 fp16; ranges `[433.4, 450.6]` vs `[507.6, 510.9]` do not overlap. |
| 3 Prefix cache | Should help (shared system+retrieval framing) | **Inconclusive / not a claimed win.** Kaggle: 488.8 vs 508.9 (prefix *lower*; ranges no overlap). AWS: 516.9 vs 472.0 (prefix *higher*; ranges no overlap). Opposite directions → unproven. |
| 4 TP=2 | Uncertain / likely disappointing (PCIe) | **Confirmed disappointing.** Mean 241.7 vs 508.9 — about half. |

---

## Rung 0 — HF naive

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

Throughput is flat across concurrency (serial `generate`). Raising concurrency
only inflates e2e latency. Not a “peak.”

| hardware | c | mean | std | min | max | e2e p50 mean | e2e p50 std |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaggle_t4_x1 | 1 | 19.6 | 0.1 | 19.5 | 19.8 | 7502 | 55 |
| kaggle_t4_x1 | 16 | 19.6 | 0.0 | 19.6 | 19.6 | 105810 | 414 |
| aws_g4dn.xlarge | 1 | 26.0 | 0.1 | 25.9 | 26.1 | 5623 | 22 |
| aws_g4dn.xlarge | 16 | 26.2 | 0.0 | 26.1 | 26.2 | 79249 | 507 |

tok/s columns = output tokens/sec.

**AWS note:** first AWS HF pass used streaming (all errors; still in CSV). Valid
numbers are the `--no-stream` re-run. At c=32, HF still had timeouts/errors —
no clean zero-error mean.

**GPU util / mem / KV %:** CSV columns exist but are empty for every logged row.
Flat-vs-scaling is from throughput/latency only.

---

## Rung 1 — vLLM continuous batching

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

| hardware | c | mean | std | min | max | e2e p50 mean | ttft p50 mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaggle_t4_x1 | 1 | 35.3 | 1.4 | 33.7 | 36.3 | 3923 | 66.5 |
| kaggle_t4_x1 | 32 | 508.9 | 1.7 | 507.6 | 510.9 | 6613 | 146.3 |
| aws_g4dn.xlarge | 1 | 34.8 | 0.1 | 34.7 | 35.0 | 4096 | 106.1 |
| aws_g4dn.xlarge | 32 | 472.0 | 0.2 | 471.7 | 472.2 | 6976 | 319.9 |

AWS cold start (container → `/health`): **206 s** — **single observation (n=1)**.

---

## Rung 2 — AWQ INT4

**Hardware:** `kaggle_t4_x1` only.

| config | c | mean | std | min | max |
|---|---:|---:|---:|---:|---:|
| AWQ | 1 | 22.0 | 0.0 | 22.0 | 22.1 |
| rung 1 fp16 | 1 | 35.3 | 1.4 | 33.7 | 36.3 |
| AWQ | 32 | 440.6 | 8.9 | 433.4 | 450.6 |
| rung 1 fp16 | 32 | 508.9 | 1.7 | 507.6 | 510.9 |

**Negative result:** AWQ slower than fp16; c=32 ranges do not overlap. Accuracy
not evaluated.

---

## Rung 3 — Prefix caching

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

| hardware | config | c | mean | std | min | max |
|---|---|---:|---:|---:|---:|---:|
| kaggle_t4_x1 | prefix | 32 | 488.8 | 4.5 | 486.1 | 494.0 |
| kaggle_t4_x1 | rung 1 | 32 | 508.9 | 1.7 | 507.6 | 510.9 |
| aws_g4dn.xlarge | prefix | 32 | 516.9 | 2.3 | 515.3 | 519.6 |
| aws_g4dn.xlarge | rung 1 | 32 | 472.0 | 0.2 | 471.7 | 472.2 |

Kaggle ranges: prefix entirely below rung 1. AWS ranges: prefix entirely above
rung 1. Opposite directions without a controlled A/B → **unproven**; do not
claim prefix as a cost or throughput win.

---

## Rung 4 — Tensor parallelism (2× T4)

**Hardware:** `kaggle_t4_x2` (PCIe, not NVLink)

| config | c | mean | std | min | max |
|---|---:|---:|---:|---:|---:|
| TP=2 | 1 | 12.7 | 0.2 | 12.5 | 12.9 |
| 1×T4 rung 1 | 1 | 35.3 | 1.4 | 33.7 | 36.3 |
| TP=2 | 32 | 241.7 | 1.6 | 240.0 | 243.1 |
| 1×T4 rung 1 | 32 | 508.9 | 1.7 | 507.6 | 510.9 |

**Negative result:** ~half the throughput of one T4. Gap ≫ within-rung SD.

---

## Infrastructure notes (Phase 3)

- Spot `g4dn.xlarge` in `us-west-2b`; compute destroyed after the session.
- GHA OIDC → ECR → SSM image URI; GPU `user_data` pulls on boot.
- Account budget actual ~$0.31 at write-up time (alarm $15 / ceiling $25).

## Instrumentation gap (GPU util / memory / KV)

Brief-required columns `gpu_util_pct`, `gpu_mem_mb`, `kv_cache_pct` are in the
CSV header but **blank on all 135 rows**. No values invented here.
