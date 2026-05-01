"""
RAG Pipeline — the core brain of Sanjeevani.

Flow:
  1. Embed query
  2. Retrieve top-k medical chunks from Qdrant
  3. Generate answer with LLM, grounded in retrieved context
  4. Return structured response with confidence and sources
"""
import time
import structlog
from prometheus_client import Histogram, Counter

from app.models.message import IncomingMessage, LLMResponse, SessionContext
from app.services.embedder import EmbedderService
from app.services.vector_store import VectorStoreService
from app.services.llm import LLMService
from app.core.config import settings

log = structlog.get_logger()

# Prometheus metrics
QUERY_LATENCY = Histogram(
    "sanjeevani_query_latency_ms",
    "End-to-end RAG query latency",
    buckets=[100, 300, 500, 800, 1200, 2000, 3000, 5000],
)
QUERY_COUNTER = Counter("sanjeevani_queries_total", "Total queries", ["channel"])
LOW_CONFIDENCE_COUNTER = Counter("sanjeevani_low_confidence_total", "Low confidence responses")


class RAGPipeline:
    def __init__(
        self,
        embedder: EmbedderService,
        vector_store: VectorStoreService,
        llm: LLMService,
    ):
        self._embedder = embedder
        self._vector_store = vector_store
        self._llm = llm

    async def run(
        self,
        message: IncomingMessage,
        session: SessionContext,
    ) -> LLMResponse:
        t0 = time.monotonic()
        QUERY_COUNTER.labels(channel=message.channel.value).inc()

        log.info(
            "rag.query",
            sender=message.sender,
            channel=message.channel,
            query_preview=message.body[:80],
        )

        # 1. Embed query
        query_vec = self._embedder.embed(message.body)

        # 2. Retrieve relevant chunks
        chunks = await self._vector_store.search(
            query_vector=query_vec,
            top_k=settings.RAG_TOP_K,
        )

        log.info(
            "rag.retrieved",
            chunk_count=len(chunks),
            top_score=round(chunks[0].score, 3) if chunks else 0,
        )

        # 3. Generate answer
        history = session.turns
        result = await self._llm.generate(
            query=message.body,
            chunks=chunks,
            history=history,
        )

        total_ms = (time.monotonic() - t0) * 1000
        QUERY_LATENCY.observe(total_ms)

        if result.flagged_low_confidence:
            LOW_CONFIDENCE_COUNTER.inc()

        log.info(
            "rag.complete",
            total_latency_ms=round(total_ms),
            llm_latency_ms=round(result.latency_ms),
            confidence=round(result.confidence, 3),
            flagged=result.flagged_low_confidence,
        )

        return result
