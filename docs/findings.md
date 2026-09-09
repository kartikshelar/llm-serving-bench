# Findings

Per-rung analysis. Negative results get equal space.

Predictions were pre-registered in the README before any Kaggle/AWS run.
Fill this file only after measured rows exist in `results/benchmarks.csv`.

## Rung 0 — HF naive

_Not yet measured._

## Rung 1 — vLLM continuous batching

_Not yet measured._

## Rung 2 — AWQ INT4

_Not yet measured._ Accuracy not evaluated in this repo.

## Rung 3 — Prefix caching

_Not yet measured._

## Rung 4 — Tensor parallelism (2× T4)

_Not yet measured._ Expected weak spot: PCIe interconnect on Kaggle.
