import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

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


def get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    if settings.openai_base_url:
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return OpenAI(api_key=settings.openai_api_key)


def embed_texts(client: OpenAI, texts: list[str], batch_size: int = 64) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        res = client.embeddings.create(model=settings.embedding_model, input=batch)
        vectors.extend([item.embedding for item in res.data])
    return vectors


def main() -> None:
    doc_dir = settings.docs_dir
    index_path = settings.vector_index_path
    index_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = load_docs(doc_dir)
    if not chunks:
        raise RuntimeError(
            "No documents found. Put .txt/.md files into data/docs and run again."
        )

    client = get_client()
    vectors = embed_texts(client, [c.text for c in chunks])

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


if __name__ == "__main__":
    main()
