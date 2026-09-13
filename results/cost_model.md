# Cost model

Dollars per million **output** tokens from measured throughput and a dated
spot price. No figure without a CSV row and a price source.

**Formula**

```
$/M output tokens = (instance_usd_per_hour / output_tokens_per_sec / 3600) * 1e6
```

Throughput = mean of three `errors=0` repeats at the concurrency that
maximizes output tok/s for that hardware×rung (see `docs/findings.md`).
Dispersion (sample SD) is shown next to tok/s; $/M uses the mean only.

This model prices **GPU instance hours only**. It excludes ALB, EBS, ECR
storage, and idle VPC — those matter for a live session but are not amortized
into the table below.

## Price source

| instance | region / AZ | product | $/hr | source | as-of |
|---|---|---|---:|---|---|
| g4dn.xlarge | us-west-2b | Linux/UNIX spot | **0.2562** | `aws ec2 describe-spot-price-history` | 2026-09-12T15:00:00Z |

Kaggle T4 time is free for this project → **no $/M** (throughput only).

## Results

| hardware | instance | $/hr | rung | concurrency chosen | out tok/s (mean±SD) | $/M output tokens | claim? |
|---|---|---:|---:|---:|---|---:|---|
| aws_g4dn.xlarge | g4dn.xlarge spot | 0.2562 | 0 | 4 | 26.2 ± 0.0 | **2.72** | yes — baseline |
| aws_g4dn.xlarge | g4dn.xlarge spot | 0.2562 | 1 | 32 | 472.0 ± 0.2 | **0.151** | yes — primary win |
| aws_g4dn.xlarge | g4dn.xlarge spot | 0.2562 | 3 | 32 | 516.9 ± 2.3 | 0.138 | **no** — arithmetic only; prefix unproven (see findings) |
| kaggle_t4_x1 | — | 0 | 0 | 4 | 19.7 ± 0.0 | n/a (free) | — |
| kaggle_t4_x1 | — | 0 | 1 | 32 | 508.9 ± 1.7 | n/a (free) | — |
| kaggle_t4_x1 | — | 0 | 2 | 32 | 440.6 ± 8.9 | n/a (free) | — |
| kaggle_t4_x1 | — | 0 | 3 | 32 | 488.8 ± 4.5 | n/a (free) | — |
| kaggle_t4_x2 | — | 0 | 4 | 32 | 241.7 ± 1.6 | n/a (free) | — |

**Read:** on this spot price, moving from HF (rung 0) to vLLM (rung 1) drops
cost per million output tokens by roughly **18×** ($2.72 → $0.151). That is the
cost claim. Rung 3’s $0.138 is left in the table for completeness but is
**not** a headline — Kaggle and AWS disagree on whether prefix beats rung 1
([`docs/findings.md`](../docs/findings.md)).

Spot prices move; re-query before quoting these dollars elsewhere.
