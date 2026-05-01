"""
Admin API — protected endpoints for operations team.
Authentication: Bearer token (set APP_SECRET_KEY in .env).
"""
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()
security = HTTPBearer()


def require_admin(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != settings.APP_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return True


class StatsResponse(BaseModel):
    vectors_count: int
    points_count: int
    qdrant_status: str


@router.get("/stats", dependencies=[Depends(require_admin)])
async def stats():
    from app.services.vector_store import VectorStoreService
    vs = VectorStoreService()
    info = await vs.collection_info()
    return info


@router.delete("/session/{channel}/{sender}", dependencies=[Depends(require_admin)])
async def clear_session(channel: str, sender: str):
    from app.services.session_store import SessionStore
    from app.models.message import Channel as Ch
    ss = SessionStore()
    ch = Ch(channel)
    await ss.clear_session(ch, sender)
    return {"status": "cleared", "channel": channel, "sender": sender}


@router.post("/test-query", dependencies=[Depends(require_admin)])
async def test_query(body: dict):
    """Quick RAG test without Twilio. POST {"query": "...", "channel": "whatsapp"}"""
    from app.models.message import IncomingMessage, Channel as Ch, SessionContext
    from app.services.embedder import EmbedderService
    from app.services.vector_store import VectorStoreService
    from app.services.llm import LLMService
    from app.rag.pipeline import RAGPipeline

    channel = Ch(body.get("channel", "whatsapp"))
    msg = IncomingMessage(channel=channel, sender="admin_test", body=body["query"])
    session = SessionContext(user_id="admin_test", channel=channel)

    pipeline = RAGPipeline(EmbedderService(), VectorStoreService(), LLMService())
    result = await pipeline.run(msg, session)
    return result.model_dump()
