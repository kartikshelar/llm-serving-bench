# AWQ diagnostic — one Kaggle T4 session

**Goal:** explain why AWQ lost at concurrency 1 (22.0 vs 35.3 tok/s), where
INT4 *should* help if narrow weights stay in the matmul.

**Hypothesis (unconfirmed until CSV rows exist):** AWQ path dequantizes to fp16
before GEMM; at short decode the dequant tax is not amortized. Same *shape* as
SourceBound’s onnxruntime fp16→fp32 on CPU — not the same bug, same lesson.

**Rules:** append-only to `results/benchmarks.csv`; hardware=`kaggle_t4_x1`;
notes must contain `AWQ_DIAG`; do not delete Phase 2 ladder rows; do not change
the locked models.

## Setup (Kaggle)

1. GPU session, Tesla T4 ×1.
2. Clone / upload this repo; `cd llm-serving-bench`.
3. Install serving deps (same as Phase 2):

```bash
pip install -r requirements.txt -r requirements-bench.txt
# plus the vLLM build you used for Phase 2 AWQ, if not already in the image
```

4. Run the protocol:

```bash
bash scripts/kaggle_awq_diag.sh
```

That will, for `max_tokens ∈ {64, 256, 1024}`:

| step | server | sweep |
|---|---|---|
| A | rung 1 fp16 | c=1, 3 repeats, `--sample-gpu` |
| B | rung 2 AWQ | c=1, 3 repeats, `--sample-gpu` |

Also writes `results/awq_kernel_inspect.txt` (module classes only — not tok/s).

## What to look for (after the CSV is back)

| Pattern in CSV | Interpretation |
|---|---|
| AWQ still slower at 64 **and** 1024 by similar % | Not just amortization of a fixed dequant tax; look at kernel path / launch overhead |
| AWQ gap **shrinks** as `max_tokens` grows | Consistent with per-step dequant overhead amortized over longer decode |
| `gpu_util_pct` much lower on AWQ at c=1 | Under-utilized GPU → kernel inefficiency / overhead, not “memory win used up” |
| Inspect log shows Marlin INT4 GEMM | Narrow arithmetic present — then dig into why c=1 still loses |
| Inspect log shows dense fp16 after dequant | Matches the hypothesized trap |

## Download

Copy `results/benchmarks.csv` (and `awq_kernel_inspect.txt`) out of Kaggle, then
ask the agent (or edit) to fill **AWQ diagnostic results** in `docs/findings.md`
from those rows only — no invented numbers.
