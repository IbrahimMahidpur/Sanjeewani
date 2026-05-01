"""
SMS channel adapter.
SMS constraints: 160 chars per segment (GSM-7), 153 for multi-part.
Strategy: compress response to fit within 3 segments (459 chars) where
possible, always hard-truncate at 5 segments (765 chars) with suffix.
"""
import textwrap
import structlog
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.adapters.base import BaseAdapter
from app.core.config import settings
from app.models.message import Channel, IncomingMessage, OutgoingMessage, LLMResponse

log = structlog.get_logger()

SMS_SEGMENT_CHARS = 153      # GSM-7 multi-part segment size
MAX_SEGMENTS = 5
MAX_SMS_CHARS = SMS_SEGMENT_CHARS * MAX_SEGMENTS   # 765 chars hard cap
IDEAL_SMS_CHARS = SMS_SEGMENT_CHARS * 3            # 459 chars ideal


def _compress_for_sms(text: str) -> str:
    """Remove WhatsApp markdown symbols and emoji, shorten aggressively."""
    # Strip markdown bold/italic
    text = text.replace("*", "").replace("_", "")
    # Strip common emoji (keep ASCII)
    import re
    text = re.sub(r"[^\x00-\x7F]+", "", text)
    # Collapse whitespace
    text = " ".join(text.split())
    return text


class SMSAdapter(BaseAdapter):
    def __init__(self):
        self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self._from = settings.TWILIO_SMS_FROM

    def parse(self, payload: dict) -> IncomingMessage:
        sender = payload.get("From", "")
        body = payload.get("Body", "").strip()
        return IncomingMessage(
            channel=Channel.SMS,
            sender=sender,
            body=body,
            message_id=payload.get("MessageSid"),
        )

    def format_response(self, result: LLMResponse, recipient: str) -> OutgoingMessage:
        body = _compress_for_sms(result.answer)

        if result.flagged_low_confidence:
            body = "INFO: " + body

        # Append brief source if space allows
        if result.chunks_used and len(body) < IDEAL_SMS_CHARS - 40:
            body += f" [Src: {result.chunks_used[0].source[:30]}]"

        # Add doctor advisory (always)
        advisory = " Consult a doctor for personal advice."
        if len(body) + len(advisory) <= MAX_SMS_CHARS:
            body += advisory

        # Hard cap
        if len(body) > MAX_SMS_CHARS:
            body = body[: MAX_SMS_CHARS - 4] + "..."

        return OutgoingMessage(
            channel=Channel.SMS,
            recipient=recipient,
            body=body,
        )

    async def send(self, message: OutgoingMessage) -> bool:
        try:
            msg = self._client.messages.create(
                from_=self._from,
                to=message.recipient,
                body=message.body,
            )
            segments = -(-len(message.body) // SMS_SEGMENT_CHARS)  # ceiling div
            log.info("sms.sent", sid=msg.sid, to=message.recipient, segments=segments)
            return True
        except TwilioRestException as e:
            log.error("sms.send_failed", error=str(e), to=message.recipient)
            return False
