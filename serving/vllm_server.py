"""Launch vLLM OpenAI-compatible server for rungs 1–4.

Wraps `vllm.entrypoints.openai.api_server` with our rung configs so the
same CLI surface works across continuous batching, AWQ, prefix cache, and TP.
"""

from __future__ import annotations

import argparse
import os
import sys

from serving.config_loader import load_rung_config, resolve_model_id


def build_vllm_argv(cfg: dict, model_id: str, host: str, port: int) -> list[str]:
    argv = [
        "vllm.entrypoints.openai.api_server",
        "--model",
        model_id,
        "--host",
        host,
        "--port",
        str(port),
        "--dtype",
        str(cfg.get("dtype", "float16")),
        "--max-model-len",
        str(cfg.get("max_model_len", 4096)),
        "--tensor-parallel-size",
        str(cfg.get("tensor_parallel_size", 1)),
        "--gpu-memory-utilization",
        str(cfg.get("gpu_memory_utilization", 0.90)),
    ]
    quant = cfg.get("quantization")
    if quant:
        argv.extend(["--quantization", str(quant)])
    if cfg.get("enable_prefix_caching"):
        argv.append("--enable-prefix-caching")
    return argv


def main() -> None:
    p = argparse.ArgumentParser(description="Start vLLM for a given rung")
    p.add_argument("--rung", type=int, required=True, choices=[1, 2, 3, 4])
    p.add_argument("--dryrun-model", action="store_true")
    p.add_argument("--model", type=str, default=None)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    cfg = load_rung_config(args.rung)
    if cfg.get("backend") != "vllm":
        raise SystemExit(f"rung {args.rung} is not a vLLM backend")

    model_id = args.model or resolve_model_id(cfg["model_ref"], dryrun=args.dryrun_model)
    argv = build_vllm_argv(cfg, model_id, args.host, args.port)
    print(f"[vllm] rung={args.rung} model={model_id}")
    print(f"[vllm] exec: python -m {' '.join(argv)}")

    # Prefer invoking the module so we stay compatible with vLLM's CLI.
    os.execvp(sys.executable, [sys.executable, "-m", *argv])


if __name__ == "__main__":
    main()
