# llm-serving-bench

Measure **throughput, latency, and cost** of serving the
[SourceBound](https://github.com/kartikshelar/SourceBound) RAG workload on GPU
across a fixed optimization ladder (HF baseline → vLLM → AWQ → prefix cache →
tensor parallelism).

**Accuracy is out of scope.** SourceBound owns accuracy claims. Serving a
different model here means those figures do not transfer. This repo never
imports or restates SourceBound accuracy numbers.

**Status:** Phase 3 in progress. Phase 1–2 numbers are in
`results/benchmarks.csv`. AWS work starts with **budget lock** ($15 alarm /
$25 ceiling) before any GPU is enabled — see `docs/aws-budget-guardrails.md`.

---

## Locked model

| Role | Model | Notes |
|---|---|---|
| Benchmark (Kaggle / AWS) | `Qwen/Qwen2.5-3B-Instruct` | Locked. Changing it invalidates all CSV rows. |
| Rung 2 AWQ | `Qwen/Qwen2.5-3B-Instruct-AWQ` | Same base, INT4 weights |
| Laptop dry-run only | `Qwen/Qwen2.5-0.5B-Instruct` | Never logged to CSV |

dtype: **fp16** (T4 / GTX 1650 are cc 7.5; bf16 not properly supported).

---

## Pre-registered predictions

Written **before** any Kaggle or AWS run. Outcomes go in `docs/findings.md`.

| Rung | Change | Prediction on this RAG workload |
|---|---|---|
| 0 | HF `generate`, serial | Slowest. Baseline by design. |
| 1 | vLLM continuous batching | Large throughput gain vs 0, especially at concurrency ≥8. |
| 2 | AWQ INT4 | Moderate throughput / memory win. Accuracy **not** measured here. |
| 3 | Prefix caching | Should help: system prompt + retrieval framing is near-constant. |
| 4 | TP=2 on 2×T4 | Uncertain / likely disappointing. Kaggle T4s are PCIe, not NVLink; interconnect may dominate for a 3B model. |

---

## Results

Every number that leaves this project must appear in `results/benchmarks.csv`
with a `hardware` label (`kaggle_t4_x1`, `kaggle_t4_x2`, or `aws_<instance>`).
Laptop timings are rejected by the logger.

| hardware | rung | concurrency | out tok/s | e2e p50 | notes |
|---|---|---|---|---|---|
| _empty until Phase 1_ | | | | | |

See also: [cost model](results/cost_model.md) · [findings](docs/findings.md)

---

## What wasn't measured (and why)

- **Accuracy** — owned by SourceBound; different model here would invalidate it
- **Speculative decoding** — cut deliberately (needs draft model; weak on long-prompt/short-output RAG)
- **Multi-node serving** — out of scope
- **Production traffic / real users** — this is a benchmark harness

---

## What didn't work

_Filled after measured negative results exist. Equal billing with wins._

---

## Architecture

```
loadgen (bench/) → OpenAI-compatible HTTP → HF server (rung 0) or vLLM (rungs 1–4) → GPU
```

Retrieval context is **frozen in the workload fixture** so only the generation
layer changes across rungs. Phase 1+ swaps `workload/dev_questions.json` for
SourceBound's 50-item dev split (same shape).

---

## Phase 0 — reproduce locally (no metered GPU)

```powershell
cd llm-serving-bench
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-bench.txt

# Stub server + reduced sweep + hardware-gate check (writes nothing to CSV)
python -m bench.dryrun --try-log-csv
```

### Optional: real 0.5B model on GTX 1650

```powershell
pip install -r requirements.txt
python -m serving.hf_server --rung 0 --dryrun-model --port 8000
# other terminal:
python -m bench.sweep --base-url http://127.0.0.1:8000 --hardware kaggle_t4_x1 `
  --model Qwen/Qwen2.5-0.5B-Instruct --rung 0 --gpu-count 1 `
  --concurrencies 1 --repeats 1 --requests-per-run 4 --no-stream
```

**Do not** pass laptop hardware labels. The example above uses `kaggle_t4_x1`
only when you are actually on Kaggle. For laptop GPU smoke tests, use
`bench.dryrun` or keep results out of `benchmarks.csv`.

### Container build (Phase 0 definition of done)

```powershell
docker build -f serving/Dockerfile -t llm-serving-bench:dev .
```

---

## Measurement protocol (Phase 1+)

- Concurrency: 1, 4, 8, 16, 32
- Repeats: 3 per configuration
- Warmup: discard first N requests (`--warmup-n`, default 2)
- Append CSV **after every run**, never buffer to session end

```powershell
python -m bench.sweep `
  --base-url http://127.0.0.1:8000 `
  --hardware kaggle_t4_x1 `
  --model Qwen/Qwen2.5-3B-Instruct `
  --rung 1 `
  --gpu-count 1
```

---

## Repo layout

See `PROJECT_BRIEF.md` §12. Terraform and GitHub Actions deploy land in Phase 3;
not started until Phase 2 is done.

---

## License / budget

AWS hard ceiling **$25**. Spot only, public subnet only, destroy every session.
No NAT Gateway.
