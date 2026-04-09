from __future__ import annotations

from pathlib import Path
from typing import Iterator

from app.core.config import settings
from app.services.native_qa_service import QAResult


class LlamaIndexUnavailableError(RuntimeError):
    pass


def _import_llamaindex():
    try:
        from llama_index.core import (
            Settings as LlamaSettings,
            SimpleDirectoryReader,
            StorageContext,
            VectorStoreIndex,
            load_index_from_storage,
        )
        from llama_index.core.node_parser import SentenceSplitter
        from llama_index.embeddings.openai_like import OpenAILikeEmbedding
        from llama_index.llms.openai_like import OpenAILike
    except ImportError as exc:
        raise LlamaIndexUnavailableError(str(exc)) from exc

    return {
        "Settings": LlamaSettings,
        "SimpleDirectoryReader": SimpleDirectoryReader,
        "StorageContext": StorageContext,
        "VectorStoreIndex": VectorStoreIndex,
        "load_index_from_storage": load_index_from_storage,
        "SentenceSplitter": SentenceSplitter,
        "OpenAILikeEmbedding": OpenAILikeEmbedding,
        "OpenAILike": OpenAILike,
    }


class LlamaIndexQAService:
    def __init__(self) -> None:
        self._index = None
        self._cached_mtime: float | None = None

    def is_available(self) -> bool:
        try:
            _import_llamaindex()
        except LlamaIndexUnavailableError:
            return False
        return True

    def _get_api_base(self) -> str:
        if settings.openai_base_url:
            return settings.openai_base_url.rstrip("/")
        return "https://api.openai.com/v1"

    def _get_persist_dir(self) -> Path:
        return settings.llamaindex_persist_dir

    def _configure_settings(self, li: dict) -> None:
        llama_settings = li["Settings"]
        llama_settings.llm = li["OpenAILike"](
            model=settings.chat_model,
            api_base=self._get_api_base(),
            api_key=settings.openai_api_key or "fake",
            is_chat_model=True,
            is_function_calling_model=False,
            temperature=0,
            context_window=16384,
        )
        llama_settings.embed_model = li["OpenAILikeEmbedding"](
            model_name=settings.embedding_model,
            api_base=self._get_api_base(),
            api_key=settings.openai_api_key or "fake",
            embed_batch_size=32,
        )
        llama_settings.text_splitter = li["SentenceSplitter"](
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )

    def _load_index(self):
        li = _import_llamaindex()
        self._configure_settings(li)

        persist_dir = self._get_persist_dir()
        if not persist_dir.exists():
            raise FileNotFoundError(
                f"LlamaIndex storage not found: {persist_dir}. Run `python scripts/ingest.py` first."
            )

        mtime = max(
            (path.stat().st_mtime for path in persist_dir.rglob("*") if path.is_file()),
            default=0.0,
        )
        if self._index is not None and self._cached_mtime == mtime:
            return self._index

        storage_context = li["StorageContext"].from_defaults(persist_dir=str(persist_dir))
        self._index = li["load_index_from_storage"](storage_context)
        self._cached_mtime = mtime
        return self._index

    @staticmethod
    def _extract_references(source_nodes: list) -> list[str]:
        references: list[str] = []
        for source_node in source_nodes or []:
            metadata = getattr(getattr(source_node, "node", None), "metadata", {}) or {}
            file_path = metadata.get("file_path") or metadata.get("source") or "unknown"
            start = metadata.get("start_char_idx")
            end = metadata.get("end_char_idx")
            if start is not None and end is not None:
                ref = f"{file_path}#{start}-{end}"
            else:
                ref = str(file_path)
            if ref not in references:
                references.append(ref)
        return references

    def answer(self, question: str) -> QAResult:
        index = self._load_index()
        query_engine = index.as_query_engine(
            similarity_top_k=max(1, settings.rag_top_k),
            streaming=False,
        )
        response = query_engine.query(question)
        return QAResult(
            answer=str(response),
            references=self._extract_references(getattr(response, "source_nodes", [])),
        )

    def stream_answer(self, question: str) -> tuple[Iterator[str], list[str]]:
        index = self._load_index()
        query_engine = index.as_query_engine(
            similarity_top_k=max(1, settings.rag_top_k),
            streaming=True,
        )
        response = query_engine.query(question)
        references = self._extract_references(getattr(response, "source_nodes", []))

        def iterator() -> Iterator[str]:
            response_gen = getattr(response, "response_gen", None)
            if response_gen is None:
                text = str(response) or "No answer generated."
                yield text
                return
            emitted = False
            for chunk in response_gen:
                if chunk:
                    emitted = True
                    yield chunk
            if not emitted:
                yield "No answer generated."

        return iterator(), references
