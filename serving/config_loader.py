"""Shared helpers for serving configs and model resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODELS_PATH = Path(__file__).resolve().parent / "models.yaml"
CONFIGS_DIR = Path(__file__).resolve().parent / "configs"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping in {path}")
    return data


def load_models() -> dict[str, Any]:
    return load_yaml(MODELS_PATH)


def resolve_model_id(model_ref: str, *, dryrun: bool = False) -> str:
    models = load_models()
    if dryrun:
        return str(models["dryrun_model"])
    key = {
        "benchmark": "benchmark_model",
        "benchmark_awq": "benchmark_model_awq",
        "dryrun": "dryrun_model",
    }.get(model_ref, model_ref)
    if key in models:
        return str(models[key])
    # Allow passing a full HF id directly
    return model_ref


def load_rung_config(rung: int) -> dict[str, Any]:
    matches = sorted(CONFIGS_DIR.glob(f"rung{rung}_*.yaml"))
    if not matches:
        raise FileNotFoundError(f"no config for rung {rung} in {CONFIGS_DIR}")
    return load_yaml(matches[0])
