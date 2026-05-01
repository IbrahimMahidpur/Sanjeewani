"""
Qdrant vector store service.
Manages collection creation, upsert, and semantic search.
"""
import uuid
import structlog
from typing import Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest,
)

from app.core.config import settings
from app.models.message import RetrievedChunk

log = structlog.get_logger()


class VectorStoreService:
    def __init__(self):
        self._client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            timeout=5,
        )
        self._collection = settings.QDRANT_COLLECTION

    async def ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = await self._client.get_collections()
        names = [c.name for c in collections.collections]
        if self._collection not in names:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            log.info("vector_store.collection_created", name=self._collection)
        else:
            log.info("vector_store.collection_exists", name=self._collection)

    async def upsert_chunks(self, chunks: list[dict]):
        """
        chunks: list of {text, source, metadata, embedding}
        """
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=chunk["embedding"],
                payload={
                    "text": chunk["text"],
                    "source": chunk["source"],
                    **chunk.get("metadata", {}),
                },
            )
            for chunk in chunks
        ]
        await self._client.upsert(
            collection_name=self._collection,
            points=points,
        )
        log.info("vector_store.upserted", count=len(points))

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter_source: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        """Semantic search returning top-k chunks."""
        query_filter = None
        if filter_source:
            query_filter = Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=filter_source))]
            )

        results = await self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            RetrievedChunk(
                text=r.payload["text"],
                source=r.payload.get("source", "unknown"),
                score=r.score,
                chunk_id=str(r.id),
            )
            for r in results
        ]

    async def collection_info(self) -> dict:
        info = await self._client.get_collection(self._collection)
        return {
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status,
        }
