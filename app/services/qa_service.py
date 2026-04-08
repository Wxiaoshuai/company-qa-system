import json
import math
from dataclasses import dataclass
from typing import Iterator

import requests

from app.core.config import settings


@dataclass
class QAResult:
    answer: str
    references: list[str]


class QAService:
    def __init__(self) -> None:
        self._cached_mtime: float | None = None
        self._chunks: list[dict] = []

    def _get_api_base(self) -> str:
        if settings.openai_base_url:
            return settings.openai_base_url.rstrip("/")
        return "https://api.openai.com/v1"

    def _get_headers(self) -> dict[str, str]:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        return {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

    def _post_json(self, endpoint: str, payload: dict) -> dict:
        response = requests.post(
            f"{self._get_api_base()}{endpoint}",
            headers=self._get_headers(),
            json=payload,
            timeout=120,
        )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
        return response.json()

    def _stream_post_lines(self, endpoint: str, payload: dict) -> Iterator[str]:
        with requests.post(
            f"{self._get_api_base()}{endpoint}",
            headers=self._get_headers(),
            json=payload,
            timeout=120,
            stream=True,
        ) as response:
            if response.status_code >= 400:
                raise RuntimeError(response.text)

            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                yield raw_line

    def _load_index_if_needed(self) -> None:
        path = settings.vector_index_path
        if not path.exists():
            raise FileNotFoundError(
                f"Vector index not found: {path}. Run `python scripts/ingest.py` first."
            )

        mtime = path.stat().st_mtime
        if self._cached_mtime == mtime and self._chunks:
            return

        data = json.loads(path.read_text(encoding="utf-8"))
        chunks = data.get("chunks", [])
        if not chunks:
            raise RuntimeError("Vector index is empty. Add docs and run ingest first.")

        self._chunks = chunks
        self._cached_mtime = mtime

    @staticmethod
    def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2, strict=False))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot / (norm1 * norm2)

    def _retrieve(self, question: str) -> list[dict]:
        self._load_index_if_needed()
        emb = self._post_json(
            "/embeddings",
            {"model": settings.embedding_model, "input": question},
        )
        q_vec = emb["data"][0]["embedding"]

        scored: list[tuple[float, dict]] = []
        for chunk in self._chunks:
            sim = self._cosine_similarity(q_vec, chunk["embedding"])
            scored.append((sim, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_k = max(1, settings.rag_top_k)
        return [item[1] for item in scored[:top_k]]

    @staticmethod
    def _build_context_text(contexts: list[dict]) -> str:
        return "\n\n".join(
            [
                f"[Source: {c['source']}#{c['chunk_index']}]\n{c['text']}"
                for c in contexts
            ]
        )

    @staticmethod
    def _build_references(contexts: list[dict]) -> list[str]:
        return [f"{c['source']}#{c['chunk_index']}" for c in contexts]

    def _build_prompts(self, question: str, contexts: list[dict]) -> tuple[str, str]:
        context_text = self._build_context_text(contexts)

        system_prompt = (
            "You are a company QA assistant. "
            "Answer strictly based on retrieved context. "
            "If information is insufficient, say you do not have enough information."
        )

        user_prompt = (
            f"Question:\n{question}\n\n"
            f"Retrieved Context:\n{context_text}\n\n"
            "Requirements:\n"
            "1) Give a concise and accurate answer.\n"
            "2) Do not fabricate facts not present in context.\n"
            "3) If uncertain, explicitly state uncertainty."
        )
        return system_prompt, user_prompt

    def answer(self, question: str) -> QAResult:
        contexts = self._retrieve(question)
        system_prompt, user_prompt = self._build_prompts(question, contexts)

        completion = self._post_json(
            "/chat/completions",
            {
                "model": settings.chat_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )

        answer_text = completion["choices"][0]["message"]["content"] or "No answer generated."
        return QAResult(answer=answer_text, references=self._build_references(contexts))

    def stream_answer(self, question: str) -> tuple[Iterator[str], list[str]]:
        contexts = self._retrieve(question)
        system_prompt, user_prompt = self._build_prompts(question, contexts)
        refs = self._build_references(contexts)

        def iterator() -> Iterator[str]:
            emitted = False
            for line in self._stream_post_lines(
                "/chat/completions",
                {
                    "model": settings.chat_model,
                    "temperature": 0,
                    "stream": True,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            ):
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break

                chunk = json.loads(data)
                if not chunk.get("choices"):
                    continue

                delta = chunk["choices"][0].get("delta", {}).get("content") or ""
                if delta:
                    emitted = True
                    yield delta

            if not emitted:
                yield "No answer generated."

        return iterator(), refs


qa_service = QAService()
