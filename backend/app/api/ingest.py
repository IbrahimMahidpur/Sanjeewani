"""
Ingest API — trigger KB ingestion via HTTP (e.g. from CI/CD).
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Security, HTTPException

from app.core.config import settings

router = APIRouter()
security = HTTPBearer()


def require_admin(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != settings.APP_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin token")


@router.post("/kb", dependencies=[Depends(require_admin)])
async def ingest_kb(background_tasks: BackgroundTasks, path: str = "data/kb"):
    """Trigger async knowledge base ingestion."""
    from app.rag.ingestor import ingest
    background_tasks.add_task(ingest, kb_path=path)
    return {"status": "ingestion_started", "path": path}
