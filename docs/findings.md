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

**Negative result (Phase 2 ladder):** AWQ slower than fp16 across the full
concurrency sweep; at c=32 ranges do not overlap (440.6 vs 508.9). Accuracy
not evaluated.

### Why c=1 hurt in Phase 2 (hypothesis → tested)

At concurrency 1, decode is memory-bandwidth-bound. INT4 *should* help if
narrow weights stay in the matmul. Phase 2 lost ~38% there (22.0 vs 35.3).
Leading hypothesis was dequant-to-fp16 before GEMM (same *shape* as SourceBound
fp16→fp32 on CPU).

### AWQ diagnostic results (`AWQ_DIAG`, 2026-09-13, `kaggle_t4_x1`)

Protocol: [`docs/awq_diag.md`](awq_diag.md). vLLM **0.29.0** (see
`results/awq_kernel_inspect.txt`). c=1, n=3, `errors=0`, `--sample-gpu`.
`max_tokens` asked ∈ {64, 256, 1024}.

| max_tokens | fp16 mean | std | min | max | AWQ mean | std | min | max | AWQ/fp16 | fp16 util% | AWQ util% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 64 | 30.9 | 6.1 | 24.3 | 36.5 | 76.1 | 1.4 | 75.3 | 77.7 | **2.46×** | 96.1 | 93.6 |
| 256 | 26.1 | 1.0 | 24.9 | 26.9 | 77.0 | 3.0 | 73.6 | 79.3 | **2.95×** | 98.7 | 98.2 |
| 1024 | 25.9 | 0.8 | 24.9 | 26.5 | 76.5 | 3.8 | 72.3 | 79.4 | **2.96×** | 99.6 | 98.7 |

GPU mem (mean): fp16 ~13.0–13.7 GB; AWQ ~13.3–13.6 GB.

**What this does and does not support**

1. **Dequant-amortization hypothesis: not supported here.** On this stack AWQ
   is *faster* at c=1 at every `max_tokens`, not slower. GPU util is high for
   both (~94–100%) — not an idle-AWQ story.
2. **Length sweep did not really lengthen decode.** e2e p50 for fp16 is ~5.3 s
   at both 256 and 1024; AWQ ~2.0 s at both. This RAG workload hits EOS early,
   so raising `max_tokens` did not buy longer decode to amortize anything.
3. **Phase 2 c=1 loss (22.0 vs 35.3) remains a real logged result** for that
   session. It does **not** reproduce on vLLM 0.29.0. Kernel inspect could not
   import classic `awq` / `awq_marlin` modules (only `awq_triton` symbols
   present) — treat the Phase 2 vs diag flip as **environment / kernel-path
   dependent**, not as “AWQ is always slower” or “always faster.”
4. **Do not silently rewrite the Phase 2 ladder.** High-concurrency Phase 2
   rows still show AWQ behind fp16 at c=32 (440.6 vs 508.9). This diagnostic
   only re-measured **c=1**.

**Interview framing:** the interesting claim is the *trap pattern* (quant only
pays if the kernel keeps the narrow dtype) plus honest evidence that on one T4
stack AWQ lost at c=1 and on a later vLLM 0.29 stack it won ~3× at c=1 — so
name the stack when you quote either number.

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
