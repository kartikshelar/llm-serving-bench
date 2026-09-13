# Findings

Per-rung analysis against pre-registered predictions in the README.

Every throughput figure is mean ± sample standard deviation over **n=3**
`errors=0` repeats from `results/benchmarks.csv` (Bessel-corrected SD).
Where a comparison is close, ranges `[min, max]` of the three repeats are
stated explicitly.

Model locked: `Qwen/Qwen2.5-3B-Instruct` (rung 2: `…-AWQ`). Accuracy not measured.

---

## Predictions versus outcomes

| Rung | Prediction | Outcome |
|---|---|---|
| 0 HF naive | Slowest baseline | **Confirmed.** Flat ~20 tok/s on Kaggle T4, ~26 on `aws_g4dn.xlarge`; does not scale with concurrency (SD ≪ 1 tok/s). |
| 1 vLLM | Large gain vs 0 at concurrency ≥8 | **Confirmed.** Peak 508.9±1.7 tok/s (`kaggle_t4_x1`, c=32) vs ~20 HF; 472.0±0.2 on `aws_g4dn.xlarge`. |
| 2 AWQ INT4 | Moderate throughput / memory win | **Falsified on throughput.** 440.6±8.9 vs 508.9±1.7 fp16 vLLM on the same T4 — gap ≫ within-rung SD. Memory/accuracy not claimed. |
| 3 Prefix cache | Should help (shared system+retrieval framing) | **Inconclusive / not a claimed win.** Kaggle c=32: 488.8±4.5 vs 508.9±1.7 (ranges `[486.1, 494.0]` vs `[507.6, 510.9]` — no overlap, prefix *lower*). AWS c=32: 516.9±2.3 vs 472.0±0.2 (ranges do not overlap, prefix *higher*). Opposite directions across platforms without a controlled A/B → do not treat as a resume win. |
| 4 TP=2 | Uncertain / likely disappointing (PCIe) | **Confirmed disappointing.** 241.7±1.6 on `kaggle_t4_x2` vs 508.9±1.7 single-T4 vLLM — about half. |

---

## Rung 0 — HF naive

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

Throughput is essentially flat across concurrency (serial `generate`): about
**19.6–19.7 tok/s** on Kaggle and **26.0–26.2 tok/s** on `aws_g4dn.xlarge`
(SD ≪ 1). Raising concurrency only inflates e2e latency. The c=1 vs c=16 rows
below are the same throughput story, not a “peak.”

| hardware | c | out tok/s (mean±SD) | e2e p50 ms (mean±SD) |
|---|---:|---|---|
| kaggle_t4_x1 | 1 | 19.6 ± 0.1 | 7502 ± 55 |
| kaggle_t4_x1 | 16 | 19.6 ± 0.0 | 105810 ± 414 |
| aws_g4dn.xlarge | 1 | 26.0 ± 0.1 | 5623 ± 22 |
| aws_g4dn.xlarge | 16 | 26.2 ± 0.0 | 79249 ± 507 |

**AWS note:** first AWS HF pass used streaming; the HF server rejects stream and
those rows are all errors (still in the CSV). Valid AWS rung-0 numbers are the
`--no-stream` re-run. At c=32, HF still showed timeouts/errors — no clean
zero-error mean at that concurrency on AWS.

**GPU util / mem / KV %:** CSV columns exist but are empty for every logged row
(never sampled during these runs). The flat-vs-scaling contrast is therefore
from throughput and latency only — serial `generate` vs continuous batching —
not from utilization traces.

---

## Rung 1 — vLLM continuous batching

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

This is the rung that worked. Continuous batching scales with concurrency;
TTFT stays in the low hundreds of ms while aggregate output tok/s rises.

| hardware | c | out tok/s (mean±SD) | e2e p50 ms (mean±SD) | ttft p50 ms (mean±SD) |
|---|---:|---|---|---|
| kaggle_t4_x1 | 1 | 35.3 ± 1.4 | 3923 ± 211 | 66.5 ± 4.8 |
| kaggle_t4_x1 | 32 | 508.9 ± 1.7 | 6613 ± 7 | 146.3 ± 0.8 |
| aws_g4dn.xlarge | 1 | 34.8 ± 0.1 | 4096 ± 13 | 106.1 ± 0.1 |
| aws_g4dn.xlarge | 32 | 472.0 ± 0.2 | 6976 ± 6 | 319.9 ± 4.1 |

AWS cold start (container start → `/health`): **206 s** — **single observation**
(n=1), logged in rung-1 CSV notes for the Phase 3 session. Worth reporting;
not a distribution.

---

## Rung 2 — AWQ INT4

**Hardware:** `kaggle_t4_x1` only (not repeated on AWS; Phase 3 reduced ladder
was rungs 0/1/3).

| c | AWQ out tok/s (mean±SD) | rung 1 fp16 (mean±SD) |
|---:|---|---|
| 1 | 22.0 ± 0.0 | 35.3 ± 1.4 |
| 32 | 440.6 ± 8.9 `[433.4, 450.6]` | 508.9 ± 1.7 `[507.6, 510.9]` |

**Why this is a negative result:** INT4 was expected to help throughput or at
least not hurt it on a memory-bound decode path. On this long-prompt /
short-output RAG fixture with vLLM, AWQ underperformed fp16 at every measured
concurrency. At c=32 the repeat ranges do not overlap. Accuracy was **not**
evaluated — do not infer quality from these rows.

---

## Rung 3 — Prefix caching

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

| hardware | c | prefix out tok/s (mean±SD) | rung 1 out tok/s (mean±SD) |
|---|---:|---|---|
| kaggle_t4_x1 | 32 | 488.8 ± 4.5 `[486.1, 494.0]` | 508.9 ± 1.7 `[507.6, 510.9]` |
| aws_g4dn.xlarge | 32 | 516.9 ± 2.3 `[515.3, 519.6]` | 472.0 ± 0.2 `[471.7, 472.2]` |

**How to read the dispersion:** on Kaggle the ~4% mean gap is larger than either
within-config SD, and the three-repeat ranges do not overlap — so “prefix did
not beat rung 1 on this Kaggle session” is supportable. On AWS the ranges also
do not overlap, but in the **opposite** direction. That platform split, without
identical images / warm-KV A/B, is why prefix cache stays **unproven** as an
optimization claim — not because the means were reported without error bars.
Do not put rung-3 $/M in a resume headline.

---

## Rung 4 — Tensor parallelism (2× T4)

**Hardware:** `kaggle_t4_x2` (PCIe, not NVLink)

| c | TP=2 out tok/s (mean±SD) | 1×T4 rung 1 (mean±SD) |
|---:|---|---|
| 1 | 12.7 ± 0.2 | 35.3 ± 1.4 |
| 32 | 241.7 ± 1.6 `[240.0, 243.1]` | 508.9 ± 1.7 `[507.6, 510.9]` |

**Why this failed:** for a 3B model the communication overhead of TP across
PCIe dominates any parallel matmul win. Two GPUs delivered about half the
throughput of one. Gap ≫ within-rung SD. Matches the pre-registered
“likely disappointing” call.

---

## Infrastructure notes (Phase 3)

- Spot `g4dn.xlarge` in `us-west-2b`; Terraform ASG mixed `g4dn`/`g5`,
  capacity-optimized; compute destroyed after the session.
- GHA OIDC → ECR → SSM image URI; GPU `user_data` pulls on boot.
- Account budget actual ~$0.31 at write-up time (alarm $15 / ceiling $25).

## Instrumentation gap (GPU util / memory / KV)

The brief required `gpu_util_pct`, `gpu_mem_mb`, and `kv_cache_pct`. Those
columns are in the CSV header, but **all 135 logged rows leave them blank** —
the harness never wrote NVML or vLLM engine stats during Phase 1–3 runs.
No utilization number is invented here. Re-instrumentation + a re-run would be
needed before any util table belongs in this file.
