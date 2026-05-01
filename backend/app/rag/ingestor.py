"""
Medical knowledge base ingestion pipeline.
Chunks documents, embeds them, and upserts to Qdrant.

Supported formats:
  - PDF (via pypdf)
  - Plain text / markdown
  - JSONL (pre-structured Q&A pairs)

Usage:
    python -m app.rag.ingestor --path data/kb/ --source "WHO Guidelines"
"""
import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Generator

import structlog

log = structlog.get_logger()

CHUNK_SIZE = 400       # tokens approximated as chars/4
CHUNK_OVERLAP = 80


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Sliding window chunker on whitespace boundaries."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += size - overlap
    return [c for c in chunks if len(c.strip()) > 50]


def read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_jsonl(path: Path) -> Generator[dict, None, None]:
    """Yield {question, answer, source} dicts from JSONL."""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_pdf(path: Path) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        log.warning("pypdf not installed; skipping PDF", path=str(path))
        return ""


def load_documents(kb_path: Path) -> list[dict]:
    """
    Returns list of {text, source, metadata} dicts ready for embedding.
    """
    docs = []
    for file in sorted(kb_path.rglob("*")):
        if not file.is_file():
            continue

        source = file.stem.replace("_", " ").title()

        if file.suffix in (".txt", ".md"):
            text = read_txt(file)
            for chunk in chunk_text(text):
                docs.append({"text": chunk, "source": source, "metadata": {"file": file.name}})

        elif file.suffix == ".pdf":
            text = read_pdf(file)
            for chunk in chunk_text(text):
                docs.append({"text": chunk, "source": source, "metadata": {"file": file.name}})

        elif file.suffix == ".jsonl":
            for item in read_jsonl(file):
                # Q&A pairs: concatenate for richer context
                text = f"Q: {item.get('question', '')}\nA: {item.get('answer', '')}"
                docs.append({
                    "text": text,
                    "source": item.get("source", source),
                    "metadata": {"file": file.name, "type": "qa_pair"},
                })

    log.info("ingestor.loaded", doc_count=len(docs))
    return docs


async def ingest(kb_path: str = "data/kb", batch_size: int = 64):
    from app.core.logging import configure_logging
    from app.services.embedder import EmbedderService
    from app.services.vector_store import VectorStoreService

    configure_logging()

    path = Path(kb_path)
    if not path.exists():
        log.error("ingestor.path_not_found", path=kb_path)
        return

    docs = load_documents(path)
    if not docs:
        log.warning("ingestor.no_docs_found")
        return

    embedder = EmbedderService()
    vs = VectorStoreService()
    await vs.ensure_collection()

    # Embed and upsert in batches
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        texts = [d["text"] for d in batch]
        embeddings = embedder.embed_batch(texts)
        chunks = [
            {**doc, "embedding": emb}
            for doc, emb in zip(batch, embeddings)
        ]
        await vs.upsert_chunks(chunks)
        log.info("ingestor.batch_done", batch=f"{i}-{i+len(batch)}", total=len(docs))

    info = await vs.collection_info()
    log.info("ingestor.complete", **info)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="data/kb")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    asyncio.run(ingest(kb_path=args.path, batch_size=args.batch_size))
