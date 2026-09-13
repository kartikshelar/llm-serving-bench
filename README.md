# llm-serving-bench

Measure **throughput, latency, and cost** of serving the
[SourceBound](https://github.com/kartikshelar/SourceBound) RAG workload on GPU
across a fixed optimization ladder (HF baseline → vLLM → AWQ → prefix cache →
tensor parallelism).

**Accuracy is out of scope.** SourceBound owns accuracy claims. Serving a
different model here means those figures do not transfer. This repo never
imports or restates SourceBound accuracy numbers.

**Status:** Phase 4 complete. Throughput figures are mean ± sample SD over
n=3 `errors=0` repeats from [`results/benchmarks.csv`](results/benchmarks.csv)
unless noted otherwise.

---

## Locked model

| Role | Model | Notes |
|---|---|---|
| Benchmark (Kaggle / AWS) | `Qwen/Qwen2.5-3B-Instruct` | Locked. Changing it invalidates all CSV rows. |
| Rung 2 AWQ | `Qwen/Qwen2.5-3B-Instruct-AWQ` | Same base, INT4 weights |
| Laptop dry-run only | `Qwen/Qwen2.5-0.5B-Instruct` | Never logged to CSV |

dtype: **fp16** (T4 / GTX 1650 are cc 7.5; bf16 not properly supported).

---

## Results

Peak sustainable **output** tok/s = concurrency that maximized mean throughput
with zero errors. Hardware label on every row. Full sweep (c=1…32) in the CSV;
dispersion detail in [`docs/findings.md`](docs/findings.md).

| hardware | rung | what | concurrency | out tok/s (mean±SD) | e2e p50 ms (mean±SD) |
|---|---:|---|---:|---|---|
| kaggle_t4_x1 | 0 | HF naive | 4 | 19.7 ± 0.0 | 27974 ± 52 |
| kaggle_t4_x1 | 1 | vLLM | 32 | 508.9 ± 1.7 | 6613 ± 7 |
| kaggle_t4_x1 | 2 | AWQ INT4 | 32 | 440.6 ± 8.9 | 7193 ± 76 |
| kaggle_t4_x1 | 3 | prefix cache | 32 | 488.8 ± 4.5 | 6599 ± 14 |
| kaggle_t4_x2 | 4 | TP=2 | 32 | 241.7 ± 1.6 | 12782 ± 231 |
| aws_g4dn.xlarge | 0 | HF naive | 4 | 26.2 ± 0.0 | 20948 ± 55 |
| aws_g4dn.xlarge | 1 | vLLM | 32 | 472.0 ± 0.2 | 6976 ± 6 |
| aws_g4dn.xlarge | 3 | prefix cache | 32 | 516.9 ± 2.3 | 6306 ± 235 |

AWS cold start (container → `/health`): **206 s** — **single observation (n=1)**,
CSV notes, Phase 3 session.

See also: [cost model](results/cost_model.md) · [findings](docs/findings.md)

---

## Pre-registered predictions versus outcomes

Written **before** any Kaggle or AWS run.

| Rung | Prediction | What happened |
|---|---|---|
| 0 HF `generate` | Slowest baseline | Confirmed — flat ~20–26 tok/s (SD ≪ 1), latency explodes with concurrency. |
| 1 vLLM batching | Large gain vs 0 at c≥8 | Confirmed — 508.9±1.7 vs ~20 HF at peak on T4. |
| 2 AWQ INT4 | Moderate throughput win | **Miss** — 440.6±8.9 vs 508.9±1.7; repeat ranges do not overlap. |
| 3 Prefix cache | Should help shared RAG prefix | **Inconclusive** — Kaggle prefix *lower* (ranges no overlap); AWS prefix *higher* (ranges no overlap). Opposite directions → not a claimed win. |
| 4 TP=2 on 2×T4 | Likely disappointing (PCIe) | Confirmed — 241.7±1.6 vs 508.9±1.7 (~half). |

---

## Cost (AWS spot)

Price: **$0.2562/hr** `g4dn.xlarge` Linux/UNIX spot, `us-west-2b`,
2026-09-12T15:00Z (`describe-spot-price-history`).

Claimed cost story is HF → vLLM only. Rung 3 is omitted here on purpose:
findings treat prefix cache as unproven (Kaggle/AWS disagree); see
[`docs/findings.md`](docs/findings.md). Raw rung-3 arithmetic lives in
[`results/cost_model.md`](results/cost_model.md) with the same caveat.

| hardware | rung | out tok/s (mean±SD) | $/M output tokens |
|---|---:|---|---:|
| aws_g4dn.xlarge | 0 | 26.2 ± 0.0 | **2.72** |
| aws_g4dn.xlarge | 1 | 472.0 ± 0.2 | **0.151** |

Method: [`results/cost_model.md`](results/cost_model.md). Kaggle is free → no $/M.

---

## What didn't work

Equal billing with wins. Detail in [`docs/findings.md`](docs/findings.md).

1. **AWQ (rung 2)** — expected a throughput or memory win; measured **lower**
   tok/s than fp16 vLLM on the same Kaggle T4 (440.6±8.9 vs 508.9±1.7). Accuracy
   not measured; do not spin this as “better, just slower.”
2. **Prefix caching (rung 3)** — shared system+retrieval framing should have
   helped. With dispersion reported: Kaggle ranges favor rung 1; AWS ranges
   favor prefix. Opposite platforms without a controlled A/B → not a resume win.
3. **Tensor parallelism on 2×T4 (rung 4)** — PCIe interconnect tax dominated.
   Two GPUs ≈ half the throughput of one (241.7±1.6 vs 508.9±1.7).
4. **HF streaming on AWS** — first Phase 3 HF sweep was all errors (server
   rejects stream). Valid numbers required `--no-stream`. Rows with errors
   remain in the CSV on purpose.
5. **Spot capacity** — `us-west-2` often had no g4dn/g5 spot for days despite
   quota. Multi-AZ + mixed instance types were required; still interruptible.

---

## What wasn't measured (and why)

- **Accuracy** — owned by SourceBound; different model here would invalidate it
- **Speculative decoding** — cut deliberately (needs draft model; weak on long-prompt/short-output RAG)
- **Multi-node serving** — out of scope
- **Production traffic / real users** — this is a benchmark harness
- **AWS rungs 2 and 4** — Phase 3 ran a reduced ladder (0/1/3) under the $25 ceiling

---

## Architecture

```
loadgen (bench/) → OpenAI-compatible HTTP → HF server (rung 0) or vLLM (rungs 1–4) → GPU
```

Retrieval context is **frozen in the workload fixture** so only the generation
layer changes across rungs. AWS path: GitHub Actions → ECR → SSM image URI →
spot ASG `user_data` pull (compute off by default).

---

## Reproduce

### Phase 0 — laptop stub (no CSV)

```powershell
cd llm-serving-bench
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-bench.txt
python -m bench.dryrun --try-log-csv
```

### Kaggle / AWS sweep

```powershell
python -m bench.sweep `
  --base-url http://127.0.0.1:8000 `
  --hardware kaggle_t4_x1 `   # or aws_g4dn.xlarge on the instance
  --model Qwen/Qwen2.5-3B-Instruct `
  --rung 1 `
  --gpu-count 1
```

Protocol: concurrency 1/4/8/16/32, 3 repeats, warmup discarded, append CSV
after every run. HF needs `--no-stream`.

### AWS infra

Budget guardrails and destroy checklist: [`terraform/README.md`](terraform/README.md).
Hard ceiling **$25**, alarm **$15**, spot only, no NAT. Deploy pipeline:
[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml).

---

## Related

- Accuracy / RAG evaluation: [SourceBound](https://github.com/kartikshelar/SourceBound)
- This repo: throughput, latency, cost, IaC, GPU serving only

---

## License / budget

AWS hard ceiling **$25**. Spot only, public subnet only, destroy every session.
No NAT Gateway.
