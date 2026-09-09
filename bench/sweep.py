"""Concurrency sweep driver.

Runs the measurement protocol: concurrency ∈ {1,4,8,16,32}, 3 repeats.
Appends one CSV row per (concurrency, repeat) after each run completes.

Requires --hardware to be a valid Kaggle/AWS label. Refuses laptop values.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bench.loadgen import run_load_sync
from bench.metrics import RunResult, append_result

DEFAULT_CONCURRENCIES = [1, 4, 8, 16, 32]
DEFAULT_REPEATS = 3


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="llm-serving-bench concurrency sweep")
    p.add_argument("--base-url", required=True, help="Serving base URL, e.g. http://127.0.0.1:8000")
    p.add_argument("--hardware", required=True, help="kaggle_t4_x1 | kaggle_t4_x2 | aws_<type>")
    p.add_argument("--model", required=True, help="Model id served (logged to CSV)")
    p.add_argument("--rung", type=int, required=True, choices=[0, 1, 2, 3, 4])
    p.add_argument("--gpu-count", type=int, default=1)
    p.add_argument("--concurrencies", type=int, nargs="+", default=DEFAULT_CONCURRENCIES)
    p.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    p.add_argument("--warmup-n", type=int, default=2)
    p.add_argument("--requests-per-run", type=int, default=None, help="Override request count")
    p.add_argument("--max-tokens", type=int, default=256)
    p.add_argument("--workload", type=str, default=None)
    p.add_argument("--csv", type=str, default=None, help="Path to benchmarks.csv")
    p.add_argument("--notes", type=str, default="")
    p.add_argument("--no-stream", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    csv_path = Path(args.csv) if args.csv else None

    for conc in args.concurrencies:
        for rep in range(1, args.repeats + 1):
            print(f"[sweep] rung={args.rung} concurrency={conc} repeat={rep}/{args.repeats}")
            report = run_load_sync(
                base_url=args.base_url,
                concurrency=conc,
                model=args.model,
                workload_path=args.workload,
                max_tokens=args.max_tokens,
                warmup_n=args.warmup_n,
                total_requests=args.requests_per_run,
                stream=not args.no_stream,
            )
            result = RunResult(
                hardware=args.hardware,
                gpu_count=args.gpu_count,
                model=args.model,
                rung=args.rung,
                concurrency=conc,
                repeat=rep,
                warmup_n=report.warmup_n,
                requests=report.requests,
                output_tokens_per_sec=round(report.output_tokens_per_sec, 4),
                total_tokens_per_sec=round(report.total_tokens_per_sec, 4),
                ttft_p50=round(report.ttft_p50, 3),
                ttft_p95=round(report.ttft_p95, 3),
                ttft_p99=round(report.ttft_p99, 3),
                e2e_p50=round(report.e2e_p50, 3),
                e2e_p95=round(report.e2e_p95, 3),
                e2e_p99=round(report.e2e_p99, 3),
                errors=report.errors,
                notes=args.notes,
            )
            written = append_result(result, path=csv_path)
            print(
                f"  -> out_tok/s={result.output_tokens_per_sec} "
                f"e2e_p50={result.e2e_p50}ms errors={result.errors} csv={written}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
