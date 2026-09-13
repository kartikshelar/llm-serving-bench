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

## Claimed result (headline)

| hardware | rung | concurrency | out tok/s (mean±SD) | $/M output tokens |
|---|---:|---:|---|---:|
| aws_g4dn.xlarge | 0 HF | 4† | 26.2 ± 0.0 | 2.72 |
| aws_g4dn.xlarge | 1 vLLM | 32 | 472.0 ± 0.2 | **0.151** |

† HF throughput is flat across concurrency; c=4 is representative, not a peak.

**Read:** vLLM cuts cost per million output tokens by roughly **18×** vs HF
($2.72 → $0.151) at this spot price. **That is the cost claim.**

## Unclaimed arithmetic (prefix cache)

| hardware | rung | concurrency | out tok/s (mean±SD) | $/M output tokens |
|---|---:|---:|---|---:|
| aws_g4dn.xlarge | 3 prefix | 32 | 516.9 ± 2.3 | 0.138 |

A further ~9% cheaper than rung 1 *if* the AWS prefix-cache result replicates
under a controlled A/B with identical images and warm KV state — **which it
has not** (on Kaggle, prefix was *lower* than rung 1; ranges did not overlap).
See [`docs/findings.md`](../docs/findings.md). Do not resume-quote $0.138.

## Kaggle (throughput only)

| hardware | rung | concurrency | out tok/s (mean±SD) | $/M |
|---|---:|---:|---|---|
| kaggle_t4_x1 | 0 | flat 1–16 | ~19.6–19.7 ± ≤0.1 | n/a |
| kaggle_t4_x1 | 1 | 32 | 508.9 ± 1.7 | n/a |
| kaggle_t4_x1 | 2 | 32 | 440.6 ± 8.9 | n/a |
| kaggle_t4_x1 | 3 | 32 | 488.8 ± 4.5 | n/a |
| kaggle_t4_x2 | 4 | 32 | 241.7 ± 1.6 | n/a |

Spot prices move; re-query before quoting these dollars elsewhere.
