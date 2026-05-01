"""
Tests for Sanjeevani backend.
Run: cd backend && pytest tests/ -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.adapters.whatsapp import WhatsAppAdapter, _format_sources
from app.adapters.sms import SMSAdapter, _compress_for_sms
from app.models.message import Channel, IncomingMessage, LLMResponse, RetrievedChunk
from app.rag.ingestor import chunk_text


# ── Chunker ───────────────────────────────────────────────────────────────────

def test_chunk_text_basic():
    text = " ".join([f"word{i}" for i in range(1000)])
    chunks = chunk_text(text, size=100, overlap=20)
    assert len(chunks) > 5
    # Each chunk should be non-trivial
    for chunk in chunks:
        assert len(chunk) > 50

def test_chunk_text_short():
    text = "This is a short text."
    chunks = chunk_text(text)
    assert len(chunks) == 1

def test_chunk_text_overlap():
    text = " ".join([f"word{i}" for i in range(200)])
    chunks = chunk_text(text, size=100, overlap=20)
    # With overlap, consecutive chunks should share words
    words_0 = set(chunks[0].split())
    words_1 = set(chunks[1].split())
    assert len(words_0 & words_1) > 0  # some overlap


# ── WhatsApp Adapter ──────────────────────────────────────────────────────────

def test_whatsapp_parse():
    with patch("app.adapters.whatsapp.Client"):
        adapter = WhatsAppAdapter()
    payload = {
        "From": "whatsapp:+919876543210",
        "Body": "What are dengue symptoms?",
        "MessageSid": "SM123",
        "ProfileName": "Rahul",
    }
    msg = adapter.parse(payload)
    assert msg.channel == Channel.WHATSAPP
    assert msg.sender == "+919876543210"  # prefix stripped
    assert msg.body == "What are dengue symptoms?"
    assert msg.profile_name == "Rahul"


def make_dummy_result(answer="Test answer", confidence=0.85, flagged=False):
    return LLMResponse(
        answer=answer,
        confidence=confidence,
        chunks_used=[
            RetrievedChunk(text="chunk text", source="WHO Guidelines", score=confidence, chunk_id="abc")
        ],
        latency_ms=400.0,
        model="test-model",
        flagged_low_confidence=flagged,
    )


def test_whatsapp_format_low_confidence():
    with patch("app.adapters.whatsapp.Client"):
        adapter = WhatsAppAdapter()
    result = make_dummy_result(confidence=0.5, flagged=True)
    out = adapter.format_response(result, "+919876543210")
    assert out.body.startswith("⚠️")


def test_whatsapp_format_sources():
    chunks = [
        RetrievedChunk(text="t", source="WHO", score=0.9, chunk_id="1"),
        RetrievedChunk(text="t", source="AIIMS", score=0.8, chunk_id="2"),
    ]
    src_str = _format_sources(chunks)
    assert "WHO" in src_str
    assert "AIIMS" in src_str


# ── SMS Adapter ───────────────────────────────────────────────────────────────

def test_sms_compress():
    text = "*Bold* _italic_ 😊 Hello world"
    compressed = _compress_for_sms(text)
    assert "*" not in compressed
    assert "_" not in compressed
    assert "😊" not in compressed
    assert "Hello world" in compressed


def test_sms_format_truncation():
    with patch("app.adapters.sms.Client"):
        adapter = SMSAdapter()
    long_answer = "A" * 1000
    result = make_dummy_result(answer=long_answer)
    out = adapter.format_response(result, "+919876543210")
    assert len(out.body) <= 765  # MAX_SMS_CHARS


def test_sms_format_advisory():
    with patch("app.adapters.sms.Client"):
        adapter = SMSAdapter()
    result = make_dummy_result(answer="Short answer.")
    out = adapter.format_response(result, "+919876543210")
    assert "doctor" in out.body.lower() or "consult" in out.body.lower()


# ── RAG Pipeline (integration-lite) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_rag_pipeline_low_confidence():
    """If all chunks have low score, pipeline should return safe fallback."""
    from app.rag.pipeline import RAGPipeline
    from app.models.message import SessionContext

    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [0.0] * 384

    mock_vs = AsyncMock()
    mock_vs.search.return_value = [
        RetrievedChunk(text="irrelevant", source="X", score=0.3, chunk_id="1")
    ]

    mock_llm = AsyncMock()

    pipeline = RAGPipeline(mock_embedder, mock_vs, mock_llm)

    msg = IncomingMessage(channel=Channel.WHATSAPP, sender="+91000", body="test query")
    session = SessionContext(user_id="+91000", channel=Channel.WHATSAPP)

    # LLM generate should be called (confidence check is inside LLMService, not pipeline)
    mock_llm.generate.return_value = LLMResponse(
        answer="I don't have reliable info.",
        confidence=0.3,
        chunks_used=[],
        latency_ms=10.0,
        model="test",
        flagged_low_confidence=True,
    )

    result = await pipeline.run(msg, session)
    assert result.flagged_low_confidence is True
