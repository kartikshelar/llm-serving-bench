"""CSV metrics logger for llm-serving-bench.

Every row must have a valid `hardware` value. Laptop timings are rejected.
Append-only: write after each run, never buffer to the end of a sweep.
"""

from __future__ import annotations

import csv
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_HARDWARE_PREFIXES = ("kaggle_t4_x1", "kaggle_t4_x2", "aws_")
FORBIDDEN_HARDWARE = frozenset(
    {
        "laptop",
        "local",
        "gtx_1650",
        "cpu",
        "dryrun",
        "stub",
    }
)

CSV_COLUMNS = [
    "run_id",
    "timestamp",
    "hardware",
    "gpu_count",
    "model",
    "rung",
    "concurrency",
    "repeat",
    "warmup_n",
    "requests",
    "output_tokens_per_sec",
    "total_tokens_per_sec",
    "ttft_p50",
    "ttft_p95",
    "ttft_p99",
    "e2e_p50",
    "e2e_p95",
    "e2e_p99",
    "gpu_util_pct",
    "gpu_mem_mb",
    "kv_cache_pct",
    "errors",
    "notes",
]

DEFAULT_CSV_PATH = Path(__file__).resolve().parents[1] / "results" / "benchmarks.csv"


@dataclass
class RunResult:
    hardware: str
    gpu_count: int
    model: str
    rung: int
    concurrency: int
    repeat: int
    warmup_n: int
    requests: int
    output_tokens_per_sec: float
    total_tokens_per_sec: float
    ttft_p50: float
    ttft_p95: float
    ttft_p99: float
    e2e_p50: float
    e2e_p95: float
    e2e_p99: float
    gpu_util_pct: float | None = None
    gpu_mem_mb: float | None = None
    kv_cache_pct: float | None = None
    errors: int = 0
    notes: str = ""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def validate_hardware(hardware: str) -> None:
    h = hardware.strip().lower()
    if not h:
        raise ValueError("hardware must not be blank")
    if h in FORBIDDEN_HARDWARE or h.startswith("laptop"):
        raise ValueError(
            f"hardware={hardware!r} is forbidden. Laptop/dry-run timings must "
            "never be logged to results/benchmarks.csv. Valid: kaggle_t4_x1, "
            "kaggle_t4_x2, aws_<instance_type>."
        )
    if not any(h == p or h.startswith(p) for p in VALID_HARDWARE_PREFIXES):
        raise ValueError(
            f"hardware={hardware!r} is invalid. Valid: kaggle_t4_x1, "
            "kaggle_t4_x2, aws_<instance_type>."
        )


def ensure_csv_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()


def append_result(result: RunResult, path: Path | None = None) -> Path:
    """Validate and append one run. Returns the CSV path written."""
    validate_hardware(result.hardware)
    csv_path = path or DEFAULT_CSV_PATH
    ensure_csv_header(csv_path)

    row: dict[str, Any] = asdict(result)
    # Stable column order; None -> empty
    ordered = {col: "" if row.get(col) is None else row.get(col) for col in CSV_COLUMNS}

    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow(ordered)
    return csv_path


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def summarize_latencies(values_ms: list[float]) -> tuple[float, float, float]:
    s = sorted(values_ms)
    return percentile(s, 50), percentile(s, 95), percentile(s, 99)
