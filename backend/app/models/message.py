from enum import Enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    TELEGRAM = "telegram"  # future
    EMAIL = "email"  # future


class IncomingMessage(BaseModel):
    channel: Channel
    sender: str                          # phone number or user ID
    body: str
    message_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    media_url: Optional[str] = None      # WhatsApp image attachments
    profile_name: Optional[str] = None


class RetrievedChunk(BaseModel):
    text: str
    source: str
    score: float
    chunk_id: str


class LLMResponse(BaseModel):
    answer: str
    confidence: float
    chunks_used: List[RetrievedChunk]
    latency_ms: float
    model: str
    flagged_low_confidence: bool = False


class OutgoingMessage(BaseModel):
    channel: Channel
    recipient: str
    body: str
    media_url: Optional[str] = None


class ConversationTurn(BaseModel):
    role: str   # "user" | "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionContext(BaseModel):
    user_id: str
    channel: Channel
    turns: List[ConversationTurn] = []
    language: str = "en"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
