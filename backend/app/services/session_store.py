"""
Redis-backed session store for conversation context.
Keyed by channel:sender — each user gets an isolated session.
"""
import json
import structlog
from redis.asyncio import from_url as redis_from_url

from app.core.config import settings
from app.models.message import SessionContext, ConversationTurn, Channel

log = structlog.get_logger()


class SessionStore:
    def __init__(self):
        self._redis = redis_from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    def _key(self, channel: Channel, sender: str) -> str:
        return f"session:{channel.value}:{sender}"

    async def get_session(self, channel: Channel, sender: str) -> SessionContext:
        key = self._key(channel, sender)
        raw = await self._redis.get(key)
        if raw:
            data = json.loads(raw)
            return SessionContext(**data)
        return SessionContext(user_id=sender, channel=channel)

    async def save_session(self, session: SessionContext):
        key = self._key(session.channel, session.user_id)
        # Keep only last N turns to bound token count
        session.turns = session.turns[-settings.MAX_CONTEXT_TURNS * 2:]
        await self._redis.setex(
            key,
            settings.SESSION_TTL_SECONDS,
            session.model_dump_json(),
        )

    async def add_turn(
        self,
        channel: Channel,
        sender: str,
        role: str,
        content: str,
    ) -> SessionContext:
        session = await self.get_session(channel, sender)
        session.turns.append(ConversationTurn(role=role, content=content))
        await self.save_session(session)
        return session

    async def clear_session(self, channel: Channel, sender: str):
        key = self._key(channel, sender)
        await self._redis.delete(key)
        log.info("session.cleared", channel=channel, sender=sender)
