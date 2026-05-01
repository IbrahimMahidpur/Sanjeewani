"""
Embedding service using BAAI/bge-small-en-v1.5.
Single instance loaded at startup, reused for all requests.
384-dim vectors, ~33M params, runs fast on CPU.
"""
import structlog
from sentence_transformers import SentenceTransformer
from app.core.config import settings

log = structlog.get_logger()


class EmbedderService:
    def __init__(self):
        log.info("embedder.loading", model=settings.EMBEDDING_MODEL)
        self._model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device="cpu",           # swap to "cuda" if GPU available
        )
        log.info("embedder.ready")

    def embed(self, text: str) -> list[float]:
        """Embed a single string. Returns list of floats."""
        vec = self._model.encode(
            text,
            normalize_embeddings=True,  # cosine similarity ready
            show_progress_bar=False,
        )
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embed for ingestion pipeline."""
        vecs = self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=64,
            show_progress_bar=True,
        )
        return vecs.tolist()
