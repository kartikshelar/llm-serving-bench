"""Rung 0: naive HuggingFace generate — one request at a time.

OpenAI-compatible /v1/chat/completions for the bench harness.
Uses a process-wide asyncio.Lock so concurrency>1 queues rather than batches.
That is intentional: this is the slow baseline.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Any, Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from serving.config_loader import load_rung_config, resolve_model_id

app = FastAPI(title="llm-serving-bench-hf-naive")
_lock = asyncio.Lock()
_tokenizer = None
_model = None
_model_id = ""
_max_new_tokens = 256
_device = "cuda" if torch.cuda.is_available() else "cpu"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "default"
    messages: list[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: float = 0.0
    stream: bool = False


def _messages_to_text(messages: list[ChatMessage]) -> str:
    if hasattr(_tokenizer, "apply_chat_template"):
        try:
            return _tokenizer.apply_chat_template(
                [m.model_dump() for m in messages],
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:  # noqa: BLE001
            pass
    parts = []
    for m in messages:
        parts.append(f"{m.role}: {m.content}")
    parts.append("assistant:")
    return "\n".join(parts)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": "huggingface", "model": _model_id}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": _model_id, "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat(req: ChatRequest) -> dict[str, Any]:
    if req.stream:
        raise HTTPException(400, "rung0 HF server does not support streaming yet; use --no-stream")
    max_new = req.max_tokens or _max_new_tokens
    prompt = _messages_to_text(req.messages)

    async with _lock:
        t0 = time.perf_counter()
        inputs = _tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(_device) for k, v in inputs.items()}
        prompt_tokens = int(inputs["input_ids"].shape[-1])

        with torch.inference_mode():
            out = await asyncio.to_thread(
                _model.generate,
                **inputs,
                max_new_tokens=max_new,
                do_sample=False,
                pad_token_id=_tokenizer.eos_token_id,
            )
        gen = out[0][prompt_tokens:]
        text = _tokenizer.decode(gen, skip_special_tokens=True)
        completion_tokens = int(gen.shape[0])
        _ = time.perf_counter() - t0

    return {
        "id": "hf-naive-1",
        "object": "chat.completion",
        "model": _model_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def load_model(model_id: str, dtype: str = "float16") -> None:
    global _tokenizer, _model, _model_id
    _model_id = model_id
    torch_dtype = torch.float16 if dtype == "float16" and _device == "cuda" else torch.float32
    print(f"[hf] loading {model_id} on {_device} dtype={torch_dtype}")
    _tokenizer = AutoTokenizer.from_pretrained(model_id)
    _model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=torch_dtype,
        device_map="auto" if _device == "cuda" else None,
    )
    if _device == "cpu":
        _model = _model.to(_device)
    _model.eval()


def main() -> None:
    global _max_new_tokens
    p = argparse.ArgumentParser()
    p.add_argument("--rung", type=int, default=0)
    p.add_argument("--dryrun-model", action="store_true", help="Use 0.5B laptop model")
    p.add_argument("--model", type=str, default=None, help="Override HF model id")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()

    cfg = load_rung_config(args.rung)
    if args.rung != 0 or cfg.get("backend") != "huggingface":
        raise SystemExit("hf_server.py is only for rung 0 (huggingface backend)")

    model_id = args.model or resolve_model_id(cfg["model_ref"], dryrun=args.dryrun_model)
    _max_new_tokens = int(cfg.get("max_new_tokens", 256))
    load_model(model_id, dtype=str(cfg.get("dtype", "float16")))
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
