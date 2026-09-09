"""Laptop / stub mode. Exercises every code path with zero GPU-platform hours.

- Spins up an in-process fake OpenAI-compatible server
- Runs a reduced concurrency sweep through loadgen
- Refuses to write to results/benchmarks.csv (hardware validation would also reject)

Use this to validate the harness before touching Kaggle or AWS.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from bench.loadgen import run_load_sync
from bench.metrics import RunResult, validate_hardware

# Synthetic timings — not real measurements. Never logged to benchmarks.csv.
FAKE_TTFT_MS = 25.0
FAKE_TOKEN_DELAY_MS = 2.0
FAKE_OUTPUT_TOKENS = 32
FAKE_PROMPT_TOKENS = 128


class _FakeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return  # quiet

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/v1/models"):
            body = json.dumps({"status": "ok", "object": "list", "data": [{"id": "stub"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode() or "{}")
        stream = bool(payload.get("stream", False))
        model = payload.get("model", "stub")

        time.sleep(FAKE_TTFT_MS / 1000.0)

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            def write_sse(obj: dict) -> None:
                self.wfile.write(f"data: {json.dumps(obj)}\n\n".encode())
                self.wfile.flush()

            for _ in range(FAKE_OUTPUT_TOKENS):
                time.sleep(FAKE_TOKEN_DELAY_MS / 1000.0)
                write_sse(
                    {
                        "id": "stub-1",
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": "x"},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
            write_sse(
                {
                    "id": "stub-1",
                    "object": "chat.completion.chunk",
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "usage": {
                        "prompt_tokens": FAKE_PROMPT_TOKENS,
                        "completion_tokens": FAKE_OUTPUT_TOKENS,
                        "total_tokens": FAKE_PROMPT_TOKENS + FAKE_OUTPUT_TOKENS,
                    },
                }
            )
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        time.sleep(FAKE_OUTPUT_TOKENS * FAKE_TOKEN_DELAY_MS / 1000.0)
        body = {
            "id": "stub-1",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "x" * FAKE_OUTPUT_TOKENS},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": FAKE_PROMPT_TOKENS,
                "completion_tokens": FAKE_OUTPUT_TOKENS,
                "total_tokens": FAKE_PROMPT_TOKENS + FAKE_OUTPUT_TOKENS,
            },
        }
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _start_server(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), _FakeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dry-run harness (no GPU, no CSV writes)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--concurrencies", type=int, nargs="+", default=[1, 4])
    p.add_argument("--requests-per-run", type=int, default=8)
    p.add_argument("--warmup-n", type=int, default=1)
    p.add_argument(
        "--try-log-csv",
        action="store_true",
        help="Intentionally attempt a CSV write to prove hardware validation rejects it",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    server = _start_server(args.port)
    base = f"http://127.0.0.1:{args.port}"
    print(f"[dryrun] stub server at {base}")
    print("[dryrun] synthetic timings only — will NOT write results/benchmarks.csv")

    try:
        for conc in args.concurrencies:
            report = run_load_sync(
                base_url=base,
                concurrency=conc,
                model="dryrun-stub",
                warmup_n=args.warmup_n,
                total_requests=args.requests_per_run,
                stream=True,
                timeout_s=30.0,
            )
            print(
                f"  concurrency={conc} requests={report.requests} "
                f"out_tok/s={report.output_tokens_per_sec:.2f} "
                f"e2e_p50={report.e2e_p50:.1f}ms errors={report.errors}"
            )
            if report.errors:
                print("  ERROR: dryrun had request failures", file=sys.stderr)
                return 1

        # Prove the safety gate works.
        try:
            validate_hardware("laptop")
            print("ERROR: validate_hardware accepted 'laptop'", file=sys.stderr)
            return 1
        except ValueError as e:
            print(f"[dryrun] hardware gate OK: {e}")

        if args.try_log_csv:
            from bench.metrics import append_result

            try:
                append_result(
                    RunResult(
                        hardware="laptop",
                        gpu_count=1,
                        model="should-not-write",
                        rung=0,
                        concurrency=1,
                        repeat=1,
                        warmup_n=0,
                        requests=0,
                        output_tokens_per_sec=0,
                        total_tokens_per_sec=0,
                        ttft_p50=0,
                        ttft_p95=0,
                        ttft_p99=0,
                        e2e_p50=0,
                        e2e_p95=0,
                        e2e_p99=0,
                    )
                )
                print("ERROR: CSV write with laptop hardware succeeded", file=sys.stderr)
                return 1
            except ValueError as e:
                print(f"[dryrun] CSV reject OK: {e}")

        print("[dryrun] PASS — loadgen + sweep path + hardware gate all exercised")
        return 0
    finally:
        server.shutdown()


if __name__ == "__main__":
    # Allow `python -m bench.dryrun` from repo root
    sys.exit(main())
