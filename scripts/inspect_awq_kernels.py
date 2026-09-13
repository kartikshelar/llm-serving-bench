"""Inspect how vLLM loads AWQ vs fp16 linear layers (no throughput claim).

Run on the Kaggle GPU machine after `pip install` / vLLM is available:

  python -m scripts.inspect_awq_kernels

Prints module class names for a tiny probe. Hypothesis to check later with
measured tok/s: INT4 weights that dequantize to fp16 before GEMM pay overhead
at short decode (batch=1) and may lose to native fp16.
"""

from __future__ import annotations

import importlib
import sys


def _try_import(name: str) -> object | None:
    try:
        return importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001
        print(f"  import {name}: FAIL ({exc})")
        return None


def main() -> int:
    print("=== AWQ / vLLM kernel inspection (no benchmark numbers) ===")
    print(f"python={sys.version.split()[0]}")

    vllm = _try_import("vllm")
    if vllm is None:
        print("vLLM not installed — run this on the Kaggle serving environment.")
        return 1
    print(f"vllm={getattr(vllm, '__version__', '?')}")

    candidates = [
        "vllm.model_executor.layers.quantization.awq",
        "vllm.model_executor.layers.quantization.awq_marlin",
        "vllm.model_executor.layers.quantization.awq_triton",
        "vllm.model_executor.layers.linear",
    ]
    for mod_name in candidates:
        mod = _try_import(mod_name)
        if mod is None:
            continue
        names = [n for n in dir(mod) if "AWQ" in n or "Linear" in n or "Marlin" in n]
        print(f"  {mod_name}: {names[:20]}")

    # Concrete class resolution used by vLLM's AWQ config, if present.
    try:
        from vllm.model_executor.layers.quantization.awq import AWQConfig

        methods = [m for m in dir(AWQConfig) if not m.startswith("_")]
        print(f"AWQConfig methods: {methods}")
        if hasattr(AWQConfig, "get_quant_method"):
            print("AWQConfig.get_quant_method: present")
    except Exception as exc:  # noqa: BLE001
        print(f"AWQConfig probe: {exc}")

    print(
        "\nInterpretation guide (not a measurement):\n"
        "- If the active path is Marlin/INT4 GEMM keeping narrow weights in the\n"
        "  matmul, short decode at c=1 should not lose badly to fp16.\n"
        "- If the path dequantizes to fp16/fp32 then calls a dense GEMM, c=1\n"
        "  short outputs can lose to fp16 (dequant tax not amortized).\n"
        "Confirm only with tok/s rows in results/benchmarks.csv."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
