"""
Adapter registry — maps Channel enum to concrete adapter instance.
Add new channels here without touching any other core files.
"""
from functools import lru_cache
from app.models.message import Channel
from app.adapters.base import BaseAdapter
from app.adapters.whatsapp import WhatsAppAdapter
from app.adapters.sms import SMSAdapter


@lru_cache
def get_adapter(channel: Channel) -> BaseAdapter:
    registry = {
        Channel.WHATSAPP: WhatsAppAdapter,
        Channel.SMS: SMSAdapter,
        # Channel.TELEGRAM: TelegramAdapter,   # future
        # Channel.EMAIL: EmailAdapter,          # future
    }
    cls = registry.get(channel)
    if not cls:
        raise ValueError(f"No adapter registered for channel: {channel}")
    return cls()
