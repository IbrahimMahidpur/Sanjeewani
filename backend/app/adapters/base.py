"""
Abstract channel adapter.
All channel adapters implement this interface, enabling
zero-core-change extensibility for new channels.
"""
from abc import ABC, abstractmethod
from app.models.message import IncomingMessage, OutgoingMessage, LLMResponse


class BaseAdapter(ABC):
    """
    Adapter contract:
      parse()  — raw webhook payload → IncomingMessage
      format() — LLMResponse → channel-specific OutgoingMessage
      send()   — deliver OutgoingMessage via channel API
    """

    @abstractmethod
    def parse(self, payload: dict) -> IncomingMessage:
        """Parse raw webhook payload into canonical IncomingMessage."""
        ...

    @abstractmethod
    def format_response(self, result: LLMResponse, recipient: str) -> OutgoingMessage:
        """Format LLM result into channel-appropriate OutgoingMessage."""
        ...

    @abstractmethod
    async def send(self, message: OutgoingMessage) -> bool:
        """Send message via channel. Returns True on success."""
        ...
