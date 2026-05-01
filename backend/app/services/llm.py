"""
LLM inference service.
Uses OpenAI-compatible API — works with:
  - Groq (fastest free tier, recommended for hackathon/MVP)
  - Together.ai
  - vLLM (self-hosted BioMistral-7B or fine-tuned model)
  - OpenAI GPT-4o
"""
import time
import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.message import RetrievedChunk, LLMResponse

log = structlog.get_logger()

SYSTEM_PROMPT = """You are Sanjeevani, a trusted health information assistant serving users in India via WhatsApp and SMS.

RULES (non-negotiable):
1. Answer ONLY from the provided medical context. Do NOT hallucinate facts.
2. Always recommend consulting a licensed doctor for diagnosis, treatment, or emergencies.
3. Never prescribe specific drug dosages or claim to diagnose conditions.
4. Be empathetic, clear, and concise — users may have low health literacy.
5. If the context doesn't contain enough information, say so honestly.
6. For emergencies (chest pain, stroke, severe bleeding), immediately advise calling 112.

Response format:
- Lead with the direct answer.
- Keep responses under 300 words.
- Use simple language (8th-grade reading level).
- End with: "⚕️ Please consult a doctor for personal medical advice."
"""

LOW_CONFIDENCE_RESPONSE = (
    "I don't have reliable information to answer that specific question. "
    "Please consult a qualified doctor or visit your nearest health center. "
    "For emergencies, call 112 immediately.\n\n"
    "⚕️ Please consult a doctor for personal medical advice."
)


class LLMService:
    def __init__(self):
        self._client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        self._model = settings.LLM_MODEL

    def _build_context_block(self, chunks: list[RetrievedChunk]) -> str:
        parts = []
        for i, c in enumerate(chunks, 1):
            parts.append(f"[Source {i}: {c.source}]\n{c.text}")
        return "\n\n".join(parts)

    def _build_chat_history(self, turns: list) -> list[dict]:
        """Convert session turns to OpenAI message format."""
        messages = []
        for turn in turns:
            messages.append({"role": turn.role, "content": turn.content})
        return messages

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
    )
    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        history: list = None,
    ) -> LLMResponse:
        t0 = time.monotonic()
        history = history or []

        # Confidence check: if best chunk score is too low, don't hallucinate
        max_score = max((c.score for c in chunks), default=0.0)
        if max_score < settings.CONFIDENCE_THRESHOLD:
            log.warning("llm.low_confidence", max_score=max_score, query=query[:60])
            return LLMResponse(
                answer=LOW_CONFIDENCE_RESPONSE,
                confidence=max_score,
                chunks_used=chunks,
                latency_ms=(time.monotonic() - t0) * 1000,
                model=self._model,
                flagged_low_confidence=True,
            )

        context = self._build_context_block(chunks)
        user_message = (
            f"Medical context:\n{context}\n\n"
            f"Question: {query}"
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self._build_chat_history(history[-6:]))  # last 3 turns
        messages.append({"role": "user", "content": user_message})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            stream=False,
        )

        answer = response.choices[0].message.content.strip()
        latency_ms = (time.monotonic() - t0) * 1000

        log.info(
            "llm.generated",
            latency_ms=round(latency_ms),
            tokens=response.usage.total_tokens if response.usage else 0,
            model=self._model,
        )

        return LLMResponse(
            answer=answer,
            confidence=max_score,
            chunks_used=chunks,
            latency_ms=latency_ms,
            model=self._model,
            flagged_low_confidence=False,
        )
