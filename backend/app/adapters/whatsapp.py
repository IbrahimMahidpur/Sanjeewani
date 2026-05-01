"""
WhatsApp channel adapter.
Parses Twilio WhatsApp webhooks and sends rich-formatted responses.
WhatsApp supports: bold (*text*), italic (_text_), emoji, URLs.
"""
import structlog
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.adapters.base import BaseAdapter
from app.core.config import settings
from app.models.message import Channel, IncomingMessage, OutgoingMessage, LLMResponse

log = structlog.get_logger()

MAX_WHATSAPP_CHARS = 4096   # WhatsApp message limit


def _format_sources(chunks, max_sources: int = 3) -> str:
    """Render source citations in WhatsApp-friendly format."""
    seen = []
    for c in chunks[:max_sources]:
        src = c.source
        if src not in seen:
            seen.append(src)
    if not seen:
        return ""
    return "\n\n📚 *Sources:* " + " | ".join(seen)


class WhatsAppAdapter(BaseAdapter):
    def __init__(self):
        self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self._from = settings.TWILIO_WHATSAPP_FROM

    def parse(self, payload: dict) -> IncomingMessage:
        """Parse Twilio WhatsApp webhook form data."""
        sender_raw = payload.get("From", "")
        # Strip "whatsapp:" prefix from Twilio
        sender = sender_raw.replace("whatsapp:", "")
        body = payload.get("Body", "").strip()
        media_url = payload.get("MediaUrl0")

        return IncomingMessage(
            channel=Channel.WHATSAPP,
            sender=sender,
            body=body,
            message_id=payload.get("MessageSid"),
            media_url=media_url,
            profile_name=payload.get("ProfileName"),
        )

    def format_response(self, result: LLMResponse, recipient: str) -> OutgoingMessage:
        """
        Format for WhatsApp:
        - Rich text with asterisks for bold
        - Source citations appended
        - Warning emoji for low-confidence
        """
        body = result.answer

        if result.flagged_low_confidence:
            body = f"⚠️ {body}"

        sources_str = _format_sources(result.chunks_used)
        body += sources_str

        # Truncate hard limit
        if len(body) > MAX_WHATSAPP_CHARS:
            body = body[: MAX_WHATSAPP_CHARS - 3] + "..."

        return OutgoingMessage(
            channel=Channel.WHATSAPP,
            recipient=f"whatsapp:{recipient}",
            body=body,
        )

    async def send(self, message: OutgoingMessage) -> bool:
        try:
            msg = self._client.messages.create(
                from_=self._from,
                to=message.recipient,
                body=message.body,
            )
            log.info("whatsapp.sent", sid=msg.sid, to=message.recipient)
            return True
        except TwilioRestException as e:
            log.error("whatsapp.send_failed", error=str(e), to=message.recipient)
            return False
