# llm-serving-bench — Project Brief

**Owner:** Kartik Pradip Shelar
**Status:** Phase 2 in progress — rung 2 (AWQ) next on Kaggle
**Created:** 2026-09-05
**Purpose of this file:** complete, standalone context for building this project.
Anyone (or any agent) reading only this file should be able to start work.

---

## 1. Why this project exists

Kartik is an MS CS student at USC (graduating May 2027) applying to US ML
engineering, ML infrastructure, and SWE roles. His existing portfolio is strong
on research, evaluation methodology, and honest negative results. It has a
specific, identifiable hole:

- No hyperscaler cloud experience (no AWS / GCP / Azure anywhere)
- No infrastructure-as-code
- No GPU serving or inference optimization at the LLM level
- No throughput, latency-under-load, or cost-per-token numbers
- No autoscaling, no deployment pipeline beyond a single Render container

Nearly every ML infrastructure job description asks for these. This project
exists to close that hole with real, measured, defensible evidence.

**It is not a tutorial reproduction.** The differentiating output is the
measurement discipline and the honest reporting of which optimizations did
nothing on this workload.

### The story this project must be able to tell

> "I deployed a RAG service on a 512MB CPU container, hit OOM, diagnosed it to
> PyTorch resident memory, tried fp16 (which failed, because onnxruntime
> converts fp16 back to fp32 on CPU), and shipped int8 ONNX at 279MB with the
> accuracy cost documented. Then I asked what it takes to serve that same
> workload properly on a GPU, and measured it."

That first half is the existing SourceBound project. This project is the second
half. The shape is identical and deliberate: constraint, wrong first fix,
measurement that explains why, honest accounting of the tradeoff.

---

## 2. Non-negotiable rules

These come from a documented history of resume fabrication errors. They are not
stylistic preferences.

1. **Every number that leaves this project must be traceable to a logged run.**
   If it is not in `results/benchmarks.csv`, it does not go in the README and it
   does not go on a resume.
2. **Every number is labeled with the hardware it came from.** A number measured
   on a Kaggle T4 is not an AWS number. Never present one as the other.
3. **This project does not touch accuracy.** SourceBound owns accuracy claims
   (48.4% when it commits vs 30.6% baseline). Those numbers came from a
   Groq-hosted setup with different models. Serving a different model locally
   invalidates them. This repo owns throughput, latency, and cost only. State
   this boundary explicitly in both READMEs.
4. **Negative results get equal billing.** If a rung does not help, that goes in
   the results table and gets a paragraph explaining why. This is the most
   valuable output of the project, not an embarrassment.
5. **No claim of production traffic, real users, or scale not actually run.**
   This is a benchmark harness, described as such.

---

## 3. Scope

### In scope

- Serve an LLM with vLLM against the SourceBound RAG workload
- Four optimization rungs, each measured independently
- Load testing across a concurrency sweep
- AWS deployment with Terraform (infrastructure-as-code)
- CI/CD via GitHub Actions
- CloudWatch monitoring, cold-start measurement, autoscaling
- Cost model: dollars per million tokens per rung per instance type
- Written analysis of what helped, what didn't, and why

### Explicitly out of scope

Do not add these mid-build. Scope creep is the main failure mode.

- **Speculative decoding.** Cut deliberately. Needs a separate draft model, is
  the fiddliest rung, and helps least on RAG-shaped workloads (long prompt,
  short output).
- Multi-node / multi-instance distributed serving
- Any UI beyond what SourceBound already has
- Fine-tuning or training of any kind
- Accuracy evaluation (owned by SourceBound)
- Recommender systems (a possible later project, not this one)

---

## 4. Relationship to SourceBound

**SourceBound repo:** github.com/kartikshelar/SourceBound (public)
**SourceBound live:** https://sourcebound.onrender.com

SourceBound is an agentic FastAPI support assistant that answers FastAPI usage
questions from official docs plus answered GitHub Discussions, with citations.
Relevant properties:

- LangGraph flow: `route → retrieve → assess → answer | escalate`
- Corpus: 1,645 doc chunks from 143 markdown files (FastAPI pinned at 0.119.1),
  plus 3,667 indexed GitHub Discussions
- Frozen 249-item eval set (50 dev / 199 locked test), committed with a manifest
  recording every filter parameter
- Retrieval: local `bge-base-en-v1.5` embeddings, dense top-k

**This project reuses the workload, not the repo.**

Reuse the corpus and the eval questions as the traffic source. Do not merge the
two projects. Reasons:

- SourceBound's claim is "the agent knows what it doesn't know" (selection
  behavior). This project's claim is "make it fast and cheap under real
  constraints." Merging makes neither land.
- Two clean repos give two clean resume lines instead of one muddy one.

**Why reuse rather than invent a workload:**

- RAG request shape (long prompt, short output) determines everything about the
  results. Prefix caching only helps because the system prompt repeats. Generic
  prompts would produce meaningless numbers.
- The eval set was frozen before there was any stake in speed results, so nobody
  can reasonably ask whether the questions were cherry-picked.

**Cross-link:** this README opens by stating it serves the SourceBound RAG
stack and links to that repo. SourceBound's README gets a link back.

---

## 5. Architecture

```
  load generator (Locust or k6)
            │
            ▼
  FastAPI layer (SourceBound retrieval path)
            │
            ├── retrieval: bge-base-en-v1.5, dense top-k, Chroma
            │
            ▼
  vLLM server (OpenAI-compatible endpoint)
            │
            ▼
       GPU (T4 / AWS)
```

Keep the retrieval path fixed across all rungs. Only the generation layer
changes. Otherwise the comparison is confounded.

---

## 6. The optimization ladder

Each rung is measured independently against the same workload and the same
concurrency sweep.

| # | Rung | What it changes | Expected effect on this workload |
|---|---|---|---|
| 0 | Naive HuggingFace `generate` | one request at a time | baseline, slowest by design |
| 1 | vLLM continuous batching | requests batched dynamically | large throughput gain expected |
| 2 | INT4 weight quantization (AWQ) | smaller weights, less memory traffic | gain expected, accuracy untested here |
| 3 | Prefix caching | reuses KV cache for repeated prompt prefix | should help — RAG system prompt is near-constant |
| 4 | Tensor parallelism (2× T4) | model split across two GPUs | uncertain — interconnect may dominate |

**Predictions are written down before running.** Record them in the README as
pre-registered expectations, then report what actually happened. This mirrors
the pre-registered falsification criteria used in Kartik's RA work and is a
genuine differentiator.

Rung 4 is the most likely to disappoint. Kaggle's two T4s communicate over PCIe,
not NVLink. If tensor parallelism makes things slower, that is a finding worth
writing up, not a failure.

---

## 7. Hardware plan

Three environments. Each has a fixed job. Do not blur them.

| Environment | Hardware | Job | Notes |
|---|---|---|---|
| Laptop | NVIDIA GTX 1650, ~4GB VRAM | development and debugging only | compute capability 7.5, same generation as T4 — code that runs here runs on Kaggle |
| Kaggle | 2× Tesla T4 16GB | all five rungs, full sweep | ~30 GPU-hr/week free, 12-hour sessions |
| AWS | spot GPU instance | infrastructure + hardware-matched validation | budget-constrained, see §10 |

### Why the laptop matters

4GB is too small to benchmark anything meaningful. It is ideal for the thing
that actually consumes time: getting the load generator, sweep driver, CSV
logger, and container build working. Debug against a ~0.5B model that fits in
4GB. Every code path should run locally before touching Kaggle or AWS.

This mirrors the dry-run pattern from Kartik's SpectralKD project, which
auto-detects unresolvable cluster paths and synthesizes data so every code path
runs locally before consuming server GPU hours. Same idea, same reason.

**Laptop caveat:** the GTX 16-series has no tensor cores, so fp16 gives no
speedup there. Fine for correctness, useless for performance measurement. Never
log a laptop timing as a result.

### Why not the lab V100

Kartik has access to an 8× Tesla V100-32GB lab server through his USC Research
Assistant role. It was considered and rejected:

- V100 is compute capability **7.0**. AWQ INT4 requires **7.5+**. Rung 2 would
  not run.
- vLLM has been progressively dropping Volta support.
- Single-GPU use gives no tensor parallelism data point.
- It is research compute allocated to the neuroimaging project. Using it for a
  personal portfolio project is a permission question, not a technical one.
- A fourth environment means a fourth setup tax (CUDA versions, driver quirks,
  storage paths) for no coverage gain.

Kaggle's 2× T4 covers the entire ladder. The V100 covers less.

### Known hardware constraints

- T4 and GTX 1650 are compute capability 7.5: AWQ INT4 works, **FP8 does not**
  (needs Ada or Hopper)
- bfloat16 is not properly supported on either — **use fp16**
- 16GB VRAM caps the model at roughly 7B in INT4 or 3B in fp16

**Pick one model that fits the smallest benchmarking card and never change it.**
Changing models mid-project invalidates every prior measurement.

---

## 8. Measurement protocol

### Sweep design

- **Concurrency levels:** 1, 4, 8, 16, 32
- **Repeats:** 3 per configuration
- **Workload:** the SourceBound eval questions (50-item dev split)
- **Warmup:** discard the first N requests per run; record N

Three repeats at five levels is what allows a claim that a difference is real
rather than noise. Do not cut this to save time. Kartik's RA work already
reports MINiT at 0.873 ± 0.008 over nine seed replicates; a throughput benchmark
with n=1 per config invites exactly the question he already knows how to answer.

### Metrics per run

- Tokens per second (output tokens, and total tokens separately)
- Time to first token (p50, p95, p99)
- End-to-end latency (p50, p95, p99)
- GPU utilization
- GPU memory used
- KV cache occupancy where vLLM exposes it
- Requests per second, and error/timeout count

### The CSV

Single append-only file: `results/benchmarks.csv`. Append from the first run,
not at the end.

```
run_id,timestamp,hardware,gpu_count,model,rung,concurrency,repeat,
warmup_n,requests,output_tokens_per_sec,total_tokens_per_sec,
ttft_p50,ttft_p95,ttft_p99,e2e_p50,e2e_p95,e2e_p99,
gpu_util_pct,gpu_mem_mb,kv_cache_pct,errors,notes
```

`hardware` values: `kaggle_t4_x1`, `kaggle_t4_x2`, `aws_<instance_type>`.
Never leave it blank. Never use a laptop value.

**The `notes` column is where the value is.** When a rung does nothing, write
down why you think that is immediately, while the run is fresh. Those
observations are what make this project original rather than a reproduction.

---

## 9. AWS infrastructure

### What Terraform must create

- VPC with a **public subnet only** (see cost guardrails — no NAT Gateway)
- Security group, minimal ingress
- ECR repository for the container image
- S3 bucket for model artifacts and the Chroma index
- GPU instance via spot request (`g4dn.xlarge` or `g5.xlarge`)
- Application Load Balancer
- Autoscaling triggered on queue depth
- CloudWatch metrics and alarms

### Pipeline

GitHub Actions: build image → push to ECR → deploy.

### AWS-specific measurements

- **Cold start time for a GPU node.** From scale-out trigger to first served
  request. This is genuinely painful in practice and rarely written down. It is
  a finding.
- **Hardware-matched validation run.** Re-run a reduced three-rung ladder on the
  AWS GPU. This is what makes it legitimate to say "served on AWS at X tok/s"
  with X being an AWS number.

---

## 10. Cost guardrails

**Hard budget ceiling: $25.** Kartik is a student. This is not flexible.

Set these up **before writing any Terraform**:

- [ ] AWS Budgets alarm at **$15**, email alert
- [ ] Public subnet only — **no NAT Gateway** (~$0.045/hr plus data processing,
      and invisible because nothing visibly runs on it; a classic silent drain)
- [ ] **Spot instances only**, never on-demand
- [ ] `terraform destroy` at the end of **every single session**, no exceptions —
      not "when the project is done"
- [ ] Never leave a GPU instance running overnight (a GPU plus ALB left up for a
      weekend is $30+, over budget by itself)

Expected: spot G-instance pricing typically runs 60–70% below on-demand.
Roughly 4–6 GPU-hours across 3–4 sessions, plus ~$1 of storage. Verify current
pricing against the AWS calculator before committing.

**Check for credits first.** AWS new-account credits, GitHub Student Developer
Pack, Azure for Students, and GCP free trial have all historically offered
meaningful amounts. If any is available, the budget math changes entirely.

### Kaggle friction fix

Upload model weights and the AWQ-quantized artifact as a Kaggle dataset once.
Otherwise several GB re-download at the start of every session, costing ~20
minutes each time instead of ~3.

---

## 11. Phase plan

Each phase has a definition of done. Do not start the next until the current one
is met.

### Phase 0 — Laptop, development
**Done when:** the full pipeline runs end to end against a ~0.5B model on the
GTX 1650. Load generator works. Sweep driver works. CSV logger writes valid
rows. Container builds. Zero GPU-platform hours consumed.

### Phase 1 — Kaggle, baseline and batching
**Done when:** `results/benchmarks.csv` contains rung 0 and rung 1 at all five
concurrency levels with three repeats each, labeled `kaggle_t4_x1`.
**This alone is resume-worthy.** If the project stalls, ship this.

### Phase 2 — Kaggle, remaining rungs
**Done when:** rungs 2, 3, and 4 are in the CSV. Rung 4 labeled
`kaggle_t4_x2`. AWQ artifact stored as a Kaggle dataset.

### Phase 3 — AWS, infrastructure
**Done when:** `terraform apply` brings up the full stack from scratch, the
GitHub Actions pipeline deploys to it, cold start is measured, a reduced
three-rung ladder is in the CSV labeled `aws_*`, and `terraform destroy` tears
it all down cleanly. Total spend under $25.

### Phase 4 — Write-up
**Done when:** README contains the results table, the pre-registered predictions
versus outcomes, the cost model, the failure analysis, and the hardware labels.
Cross-links to SourceBound are in place in both repos.

**Estimated total:** 3–4 weekends, roughly 25 hours. Compute is not the
bottleneck; the full sweep is 2–3 hours of actual GPU time. Debugging is the
other 20-plus hours.

---

## 12. Repository structure

```
llm-serving-bench/
├── README.md
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── serving/
│   ├── Dockerfile
│   ├── vllm_server.py
│   └── configs/          # one config per rung
├── bench/
│   ├── loadgen.py        # or locustfile.py / k6 script
│   ├── sweep.py          # drives the concurrency sweep
│   ├── metrics.py        # collection + CSV append
│   └── dryrun.py         # laptop/stub mode, no GPU required
├── results/
│   ├── benchmarks.csv
│   └── cost_model.md
├── .github/workflows/
│   └── deploy.yml
└── docs/
    └── findings.md       # per-rung analysis, including what failed
```

---

## 13. README requirements

The README is the deliverable a recruiter or interviewer actually reads.

**Must contain:**

1. One-line statement of what this is and that it serves the SourceBound RAG
   workload, with a link
2. Explicit boundary note: this repo measures throughput, latency, and cost.
   SourceBound owns accuracy. Serving different models here means SourceBound's
   accuracy figures do not transfer.
3. Results table with **hardware labeled on every row**
4. Pre-registered predictions versus what actually happened
5. Cost model: dollars per million tokens per rung per instance type
6. **A "What didn't work" section.** Give it real space.
7. Reproduction instructions
8. Explicit statement of what was not measured and why (accuracy, speculative
   decoding, multi-node)

---

## 14. What to report back to Kartik

After **Phase 1**, hand over `results/benchmarks.csv` raw. Do not summarize it
into resume bullets. Bullets get drafted separately against the evidence-bank
process, with hardware labels attached to every figure.

Nothing from this project enters `evidence-bank.md` until numbers exist in the
CSV.

---

## 15. Failure modes to watch for

| Risk | Mitigation |
|---|---|
| Scope creep (adding rungs, adding a UI, adding accuracy eval) | §3 out-of-scope list is binding |
| AWS bill overrun | §10 guardrails, set up before any Terraform |
| Model changed mid-project | Pick one model in Phase 0, never change |
| Hardware labels omitted from CSV | `hardware` is a required column; validate on write |
| Debugging on metered/shared GPU | Phase 0 exists precisely to prevent this |
| Kaggle session loss mid-sweep | Append to CSV per run, never buffer to the end |
| Confusing this repo's numbers with SourceBound's | Boundary note in both READMEs |
| Project displaces job applications | This is a side track. Applications and DSA practice remain the priority. |

---

## 16. Context on the owner (for tone and framing)

- Prefers direct output over preamble. Disagreement is welcome and expected.
- Has a documented history of resume claim errors, all traced to the same cause:
  reconstructing a fact from an earlier draft instead of reading the source.
  Always re-read the source.
- Reports negative results honestly as a matter of practice — a falsified
  proposition, a permutation null of p = 0.942 that overturned his own group's
  headline result, six measured upgrades that none beat baseline. This project
  should follow the same standard.
- Existing strengths this project is not trying to duplicate: evaluation
  methodology, representation learning research, problem framing, RAG systems.
- The gap being closed is narrow and specific: cloud, IaC, GPU serving, cost.
