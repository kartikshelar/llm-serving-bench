# Cost model

Dollars per million tokens will be filled from measured throughput and
current spot prices after Phase 1 (Kaggle) and Phase 3 (AWS) runs exist in
`results/benchmarks.csv`.

**Rule:** no cost figure without a CSV row and a dated price source.

| hardware | instance | $/hr (source, date) | rung | tok/s (CSV) | $/M output tokens |
|---|---|---|---|---|---|
| _empty until measured_ | | | | | |

## Method

```
$/M output tokens = (instance_usd_per_hour / output_tokens_per_sec / 3600) * 1e6
```

Use the concurrency level that maximizes sustainable throughput without
elevated error rates. Document which concurrency was chosen per rung.
