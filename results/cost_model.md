# Cost model

Dollars per million **output** tokens from measured throughput and a dated
spot price. No figure without a CSV row and a price source.

**Formula**

```
$/M output tokens = (instance_usd_per_hour / output_tokens_per_sec / 3600) * 1e6
```

$/M uses the **mean** tok/s (n=3, `errors=0`). Spread is shown beside it.

This model prices **GPU instance hours only** (excludes ALB, EBS, ECR, idle VPC).

## Price source

| instance | region / AZ | product | $/hr | source | as-of |
|---|---|---|---:|---|---|
| g4dn.xlarge | us-west-2b | Linux/UNIX spot | **0.2562** | `aws ec2 describe-spot-price-history` | 2026-09-12T15:00:00Z |

## Claimed cost (lead with this)

**$0.151 / M output tokens** — rung 1 vLLM on `aws_g4dn.xlarge`.

| hardware | rung | c | mean | std | min | max | $/M |
|---|---:|---:|---:|---:|---:|---:|---:|
| aws_g4dn.xlarge | **1 vLLM** | 32 | 472.0 | 0.2 | 471.7 | 472.2 | **0.151** |
| aws_g4dn.xlarge | 0 HF† | 4 | 26.2 | 0.0 | 26.2 | 26.2 | 2.72 |

† HF is flat across concurrency; c=4 is representative, not a peak.

**~18×** cheaper than HF at this spot price. **That is the only cost claim.**

## Unclaimed (prefix cache) — do not headline

Prefix is **unproven** on this workload ([`docs/findings.md`](../docs/findings.md)).
Arithmetic only, if the AWS session somehow replicated:

| hardware | rung | c | mean | std | min | max | $/M |
|---|---:|---:|---:|---:|---:|---:|---:|
| aws_g4dn.xlarge | 3 | 32 | 516.9 | 2.3 | 515.3 | 519.6 | 0.138 |

Not a resume figure. Kaggle prefix was *slower* than rung 1.

## Kaggle (throughput only; free)

| hardware | rung | c | mean | std | min | max |
|---|---:|---:|---:|---:|---:|---:|
| kaggle_t4_x1 | 0 | 1 | 19.6 | 0.1 | 19.5 | 19.8 |
| kaggle_t4_x1 | 0 | 16 | 19.6 | 0.0 | 19.6 | 19.6 |
| kaggle_t4_x1 | 1 | 32 | 508.9 | 1.7 | 507.6 | 510.9 |
| kaggle_t4_x1 | 2 | 32 | 440.6 | 8.9 | 433.4 | 450.6 |
| kaggle_t4_x1 | 3 | 32 | 488.8 | 4.5 | 486.1 | 494.0 |
| kaggle_t4_x2 | 4 | 32 | 241.7 | 1.6 | 240.0 | 243.1 |

Spot prices move; re-query before quoting dollars elsewhere.
