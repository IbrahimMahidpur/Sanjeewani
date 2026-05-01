from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    qdrant: str = "unknown"
    redis: str = "unknown"


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    vs = request.app.state.vector_store
    ss = request.app.state.session_store

    # Quick liveness checks
    try:
        info = await vs.collection_info()
        qdrant_status = f"ok ({info.get('vectors_count', 0)} vectors)"
    except Exception as e:
        qdrant_status = f"error: {e}"

    try:
        await ss._redis.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {e}"

    return HealthResponse(
        status="ok",
        qdrant=qdrant_status,
        redis=redis_status,
    )
