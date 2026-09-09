"""Async load generator against an OpenAI-compatible /v1/chat/completions endpoint.

Measures TTFT (first SSE chunk or full response start) and end-to-end latency.
Does not write CSV — callers (sweep / dryrun) own logging decisions.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from bench.metrics import summarize_latencies
from bench.workload import WorkloadItem, load_workload


@dataclass
class RequestOutcome:
    ok: bool
    ttft_ms: float
    e2e_ms: float
    output_tokens: int
    prompt_tokens: int
    error: str = ""


@dataclass
class LoadReport:
    concurrency: int
    warmup_n: int
    requests: int
    errors: int
    output_tokens_per_sec: float
    total_tokens_per_sec: float
    ttft_p50: float
    ttft_p95: float
    ttft_p99: float
    e2e_p50: float
    e2e_p95: float
    e2e_p99: float
    outcomes: list[RequestOutcome] = field(default_factory=list)


async def _one_chat(
    client: httpx.AsyncClient,
    url: str,
    item: WorkloadItem,
    model: str,
    max_tokens: int,
    stream: bool,
    timeout_s: float,
) -> RequestOutcome:
    payload: dict[str, Any] = {
        "model": model,
        "messages": item.build_messages(),
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": stream,
    }
    t0 = time.perf_counter()
    ttft_ms = float("nan")
    try:
        if stream:
            async with client.stream(
                "POST", url, json=payload, timeout=timeout_s
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    return RequestOutcome(
                        False,
                        float("nan"),
                        (time.perf_counter() - t0) * 1000,
                        0,
                        0,
                        f"HTTP {resp.status_code}: {body[:200]!r}",
                    )
                output_tokens = 0
                prompt_tokens = 0
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if ttft_ms != ttft_ms:  # NaN check
                        ttft_ms = (time.perf_counter() - t0) * 1000
                    usage = chunk.get("usage") or {}
                    if usage:
                        output_tokens = int(usage.get("completion_tokens", output_tokens))
                        prompt_tokens = int(usage.get("prompt_tokens", prompt_tokens))
                    choices = chunk.get("choices") or []
                    if choices and choices[0].get("delta", {}).get("content"):
                        # approximate token count if usage absent
                        if not usage:
                            output_tokens += 1
                e2e_ms = (time.perf_counter() - t0) * 1000
                if ttft_ms != ttft_ms:
                    ttft_ms = e2e_ms
                return RequestOutcome(True, ttft_ms, e2e_ms, output_tokens, prompt_tokens)
        else:
            resp = await client.post(url, json=payload, timeout=timeout_s)
            e2e_ms = (time.perf_counter() - t0) * 1000
            ttft_ms = e2e_ms  # non-stream: TTFT ~= E2E
            if resp.status_code >= 400:
                return RequestOutcome(
                    False,
                    ttft_ms,
                    e2e_ms,
                    0,
                    0,
                    f"HTTP {resp.status_code}: {resp.text[:200]!r}",
                )
            body = resp.json()
            usage = body.get("usage") or {}
            return RequestOutcome(
                True,
                ttft_ms,
                e2e_ms,
                int(usage.get("completion_tokens", 0)),
                int(usage.get("prompt_tokens", 0)),
            )
    except Exception as exc:  # noqa: BLE001 — surface as error count
        e2e_ms = (time.perf_counter() - t0) * 1000
        return RequestOutcome(False, ttft_ms, e2e_ms, 0, 0, str(exc))


async def run_load(
    base_url: str,
    concurrency: int,
    *,
    model: str = "default",
    workload_path: str | None = None,
    max_tokens: int = 256,
    warmup_n: int = 2,
    total_requests: int | None = None,
    stream: bool = True,
    timeout_s: float = 120.0,
) -> LoadReport:
    """Run a fixed concurrency load against base_url.

    Warmup requests are executed first and discarded from metrics.
    """
    items = load_workload(None if workload_path is None else Path(workload_path))
    n = total_requests if total_requests is not None else max(len(items), concurrency * 2)
    url = base_url.rstrip("/") + "/v1/chat/completions"

    async with httpx.AsyncClient() as client:
        # Warmup
        for i in range(warmup_n):
            await _one_chat(
                client, url, items[i % len(items)], model, max_tokens, stream, timeout_s
            )

        sem = asyncio.Semaphore(concurrency)
        outcomes: list[RequestOutcome] = []

        async def worker(idx: int) -> None:
            async with sem:
                out = await _one_chat(
                    client,
                    url,
                    items[idx % len(items)],
                    model,
                    max_tokens,
                    stream,
                    timeout_s,
                )
                outcomes.append(out)

        t_wall0 = time.perf_counter()
        await asyncio.gather(*(worker(i) for i in range(n)))
        wall_s = max(time.perf_counter() - t_wall0, 1e-9)

    ok = [o for o in outcomes if o.ok]
    errors = len(outcomes) - len(ok)
    out_tok = sum(o.output_tokens for o in ok)
    prompt_tok = sum(o.prompt_tokens for o in ok)
    ttft = [o.ttft_ms for o in ok if o.ttft_ms == o.ttft_ms]
    e2e = [o.e2e_ms for o in ok]

    ttft_p50, ttft_p95, ttft_p99 = summarize_latencies(ttft)
    e2e_p50, e2e_p95, e2e_p99 = summarize_latencies(e2e)

    return LoadReport(
        concurrency=concurrency,
        warmup_n=warmup_n,
        requests=len(outcomes),
        errors=errors,
        output_tokens_per_sec=out_tok / wall_s,
        total_tokens_per_sec=(out_tok + prompt_tok) / wall_s,
        ttft_p50=ttft_p50,
        ttft_p95=ttft_p95,
        ttft_p99=ttft_p99,
        e2e_p50=e2e_p50,
        e2e_p95=e2e_p95,
        e2e_p99=e2e_p99,
        outcomes=outcomes,
    )


def run_load_sync(**kwargs: Any) -> LoadReport:
    return asyncio.run(run_load(**kwargs))
