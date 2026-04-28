import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

# Allow running via `python scripts/ingest.py` from project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown"}


@dataclass
class Chunk:
    source: str
    chunk_index: int
    text: str


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        part = clean[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(clean):
            break
        start += step

    return chunks


def load_docs(doc_dir: Path) -> list[Chunk]:
    all_chunks: list[Chunk] = []

    files = sorted(
        [p for p in doc_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    )

    for file_path in files:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        pieces = split_text(text, settings.rag_chunk_size, settings.rag_chunk_overlap)
        for i, piece in enumerate(pieces):
            all_chunks.append(
                Chunk(
                    source=str(file_path.as_posix()),
                    chunk_index=i,
                    text=piece,
                )
            )

    return all_chunks


def get_api_base() -> str:
    if settings.openai_base_url:
        return settings.openai_base_url.rstrip("/")
    return "https://api.openai.com/v1"


def get_headers() -> dict[str, str]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }


def embed_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = requests.post(
            f"{get_api_base()}/embeddings",
            headers=get_headers(),
            json={"model": settings.embedding_model, "input": batch},
            timeout=120,
        )
        if response.status_code >= 400:
            raise RuntimeError(response.text)
        res = response.json()
        vectors.extend([item["embedding"] for item in res["data"]])
    return vectors


def build_llamaindex_from_docs() -> tuple[bool, str]:
    """
    Returns (success, message).
    """
    try:
        from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
        from llama_index.core.node_parser import SentenceSplitter
        from llama_index.embeddings.openai_like import OpenAILikeEmbedding
        from llama_index.llms import OpenAILike
        from llama_index.core import settings as ll_settings
    except Exception as e:
        return False, f"Skipped LlamaIndex persistence: import error — {type(e).__name__}: {e}"

    try:
        llm = OpenAILike(
            model=settings.chat_model,
            api_base=get_api_base(),
            api_key=settings.openai_api_key or "fake",
            is_chat_model=True,
            is_function_calling_model=False,
            temperature=0,
            context_window=16384,
        )
        embed_model = OpenAILikeEmbedding(
            model_name=settings.embedding_model,
            api_base=get_api_base(),
            api_key=settings.openai_api_key or "fake",
            embed_batch_size=32,
        )

        # Bypass resolve_llm compatibility check by setting directly
        ll_settings.Settings._llm = llm
        ll_settings.Settings._embed_model = embed_model

        splitter = SentenceSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )

        documents = SimpleDirectoryReader(
            input_dir=str(settings.docs_dir),
            recursive=True,
            required_exts=list(SUPPORTED_EXTENSIONS),
            filename_as_id=True,
        ).load_data()
        if not documents:
            return False, "LlamaIndex: no documents found."

        index = VectorStoreIndex.from_documents(
            documents, transformations=[splitter]
        )
        settings.llamaindex_persist_dir.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(settings.llamaindex_persist_dir))
        return True, f"Persisted LlamaIndex storage into {settings.llamaindex_persist_dir}"
    except Exception as e:
        import traceback
        return False, f"LlamaIndex persistence failed: {type(e).__name__}: {e}\n{traceback.format_exc()}"


def main() -> None:
    doc_dir = settings.docs_dir
    index_path = settings.vector_index_path
    index_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = load_docs(doc_dir)
    if not chunks:
        raise RuntimeError(
            "No documents found. Put .txt/.md files into data/docs and run again."
        )

    vectors = embed_texts([c.text for c in chunks])

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": settings.embedding_model,
        "dimension": len(vectors[0]) if vectors else 0,
        "chunks": [
            {
                "source": c.source,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "embedding": v,
            }
            for c, v in zip(chunks, vectors, strict=False)
        ],
    }

    index_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Ingested {len(chunks)} chunks into {index_path}")

    _, msg = build_llamaindex_from_docs()
    print(msg)


if __name__ == "__main__":
    main()
