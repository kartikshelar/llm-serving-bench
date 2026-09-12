# Findings

Per-rung analysis against pre-registered predictions in the README.
Every throughput figure below is a **mean of three repeats** with `errors=0`
from `results/benchmarks.csv`. Negative results get equal space.

Model locked: `Qwen/Qwen2.5-3B-Instruct` (rung 2: `…-AWQ`). Accuracy not measured.

---

## Predictions versus outcomes

| Rung | Prediction | Outcome |
|---|---|---|
| 0 HF naive | Slowest baseline | **Confirmed.** Flat ~20 tok/s on Kaggle T4, ~26 tok/s on `aws_g4dn.xlarge`; does not scale with concurrency. |
| 1 vLLM | Large gain vs 0 at concurrency ≥8 | **Confirmed.** Peak ~509 tok/s (`kaggle_t4_x1`, c=32) vs ~20 tok/s HF; ~472 tok/s on `aws_g4dn.xlarge`. |
| 2 AWQ INT4 | Moderate throughput / memory win | **Falsified on throughput.** Peak ~441 tok/s vs ~509 for fp16 vLLM on the same T4 — **slower**, not faster. Memory/accuracy not claimed here. |
| 3 Prefix cache | Should help (shared system+retrieval framing) | **Mixed / mostly null.** On Kaggle: peak ~489 vs ~509 for rung 1 (no win). On AWS: peak ~517 vs ~472 (small win at c=32 only). Not a clear win on this workload. |
| 4 TP=2 | Uncertain / likely disappointing (PCIe) | **Confirmed disappointing.** Peak ~242 tok/s on `kaggle_t4_x2` — about **half** single-T4 vLLM. |

---

## Rung 0 — HF naive

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

Throughput is essentially flat across concurrency (serial `generate`). Raising
concurrency only inflates e2e latency.

| hardware | c | mean out tok/s | mean e2e p50 (ms) |
|---|---:|---:|---:|
| kaggle_t4_x1 | 1 | 19.6 | 7502 |
| kaggle_t4_x1 | 16 | 19.6 | 105810 |
| aws_g4dn.xlarge | 1 | 26.0 | 5623 |
| aws_g4dn.xlarge | 16 | 26.2 | 79249 |

**AWS note:** first AWS HF pass used streaming; the HF server rejects stream and
those rows are all errors (still in the CSV). Valid AWS rung-0 numbers are the
`--no-stream` re-run. At c=32, HF still showed timeouts/errors — no clean
zero-error mean at that concurrency on AWS.

---

## Rung 1 — vLLM continuous batching

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

This is the rung that worked. Continuous batching scales with concurrency;
TTFT stays in the low hundreds of ms while aggregate output tok/s rises.

| hardware | c | mean out tok/s | mean e2e p50 (ms) | mean ttft p50 (ms) |
|---|---:|---:|---:|---:|
| kaggle_t4_x1 | 1 | 35.3 | 3923 | 67 |
| kaggle_t4_x1 | 32 | 509.0 | 6613 | 146 |
| aws_g4dn.xlarge | 1 | 34.8 | 4096 | 106 |
| aws_g4dn.xlarge | 32 | 472.0 | 6976 | 320 |

AWS cold start (container start → `/health`): **206 s** (logged in rung-1 CSV
notes for the Phase 3 session). Same GPU class (T4) as Kaggle; absolute tok/s
is in the same ballpark, not identical session-to-session.

---

## Rung 2 — AWQ INT4

**Hardware:** `kaggle_t4_x1` only (not repeated on AWS; Phase 3 reduced ladder
was rungs 0/1/3).

| c | mean out tok/s (AWQ) | mean out tok/s (rung 1 fp16) |
|---:|---:|---:|
| 1 | 22.0 | 35.3 |
| 32 | 440.6 | 509.0 |

**Why this is a negative result:** INT4 was expected to help throughput or at
least not hurt it on a memory-bound decode path. On this long-prompt /
short-output RAG fixture with vLLM, AWQ underperformed fp16 at every measured
concurrency. Accuracy was **not** evaluated — do not infer quality from these
rows.

---

## Rung 3 — Prefix caching

**Hardware:** `kaggle_t4_x1`, `aws_g4dn.xlarge`

| hardware | c | mean out tok/s (prefix) | mean out tok/s (rung 1) |
|---|---:|---:|---:|
| kaggle_t4_x1 | 32 | 488.8 | 509.0 |
| aws_g4dn.xlarge | 32 | 516.9 | 472.0 |

**Why this is mostly a negative / null result:** the shared prefix hypothesis
was reasonable for RAG, but Kaggle showed no benefit versus rung 1. AWS showed
a modest gain at high concurrency only. Treat prefix cache as unproven for
this workload until a controlled A/B with identical images and warm KV state
is re-run — not as a resume win.

---

## Rung 4 — Tensor parallelism (2× T4)

**Hardware:** `kaggle_t4_x2` (PCIe, not NVLink)

| c | mean out tok/s (TP=2) | mean out tok/s (1×T4 rung 1) |
|---:|---:|---:|
| 1 | 12.7 | 35.3 |
| 32 | 241.7 | 509.0 |

**Why this failed:** for a 3B model the communication overhead of TP across
PCIe dominates any parallel matmul win. Two GPUs delivered about half the
throughput of one. Matches the pre-registered “likely disappointing” call.

---

## Infrastructure notes (Phase 3)

- Spot `g4dn.xlarge` in `us-west-2b`; Terraform ASG mixed `g4dn`/`g5`,
  capacity-optimized; compute destroyed after the session.
- GHA OIDC → ECR → SSM image URI; GPU `user_data` pulls on boot.
- Account budget actual ~$0.31 at write-up time (alarm $15 / ceiling $25).
