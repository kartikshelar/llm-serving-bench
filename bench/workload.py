"""Workload helpers: SourceBound-shaped RAG prompts.

Phase 0 ships a synthetic fixture so every code path runs without the
SourceBound corpus. Phase 1+ should point --workload at the real 50-item
dev split exported from SourceBound (questions only; accuracy not measured).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Near-constant system prompt — why prefix caching (rung 3) should help.
SYSTEM_PROMPT = (
    "You are SourceBound, a FastAPI support assistant. Answer using only the "
    "retrieved documentation and GitHub Discussion excerpts below. Cite "
    "sources. If the evidence is insufficient, say you do not know and "
    "suggest escalation. Keep answers concise."
)

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "workload" / "dev_questions.json"


@dataclass
class WorkloadItem:
    question_id: str
    question: str
    # Retrieved context is fixed across rungs so only generation changes.
    context: str

    def build_messages(self) -> list[dict[str, str]]:
        user = (
            f"Retrieved context:\n{self.context}\n\n"
            f"Question: {self.question}\n\n"
            "Answer with citations."
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    def build_prompt(self) -> str:
        """Flattened chat-style prompt for backends without chat templates."""
        msgs = self.build_messages()
        return f"{msgs[0]['content']}\n\n{msgs[1]['content']}"


def load_workload(path: Path | None = None) -> list[WorkloadItem]:
    p = path or DEFAULT_FIXTURE
    with p.open(encoding="utf-8") as f:
        raw = json.load(f)
    items = []
    for row in raw:
        items.append(
            WorkloadItem(
                question_id=str(row["question_id"]),
                question=row["question"],
                context=row.get("context", ""),
            )
        )
    if not items:
        raise ValueError(f"workload empty: {p}")
    return items
