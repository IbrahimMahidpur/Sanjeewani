"""
Webhook endpoints for Twilio WhatsApp and SMS.
Both channels POST form-encoded data; we parse, run RAG, respond.

Twilio expects a TwiML or plain text response within 15 seconds.
We respond with 200 immediately and send the reply asynchronously.
"""
import hashlib
import hmac
import time

import structlog
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request, Response

from app.adapters.registry import get_adapter
from app.core.config import settings
from app.models.message import Channel
from app.rag.pipeline import RAGPipeline
from app.services.llm import LLMService

log = structlog.get_logger()
router = APIRouter()


def _verify_twilio_signature(request_url: str, params: dict, signature: str) -> bool:
    """Validate Twilio webhook signature to prevent spoofing."""
    if not settings.TWILIO_WEBHOOK_SECRET:
        return True  # skip validation in dev
    auth_token = settings.TWILIO_AUTH_TOKEN
    sorted_params = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    computed = hmac.new(
        auth_token.encode(), (request_url + sorted_params).encode(), hashlib.sha1
    ).digest()
    import base64
    return base64.b64encode(computed).decode() == signature


async def _handle_message(channel: Channel, payload: dict, request: Request):
    """Core handler: parse → session → RAG → format → send."""
    adapter = get_adapter(channel)
    message = adapter.parse(payload)

    # Guard: empty messages (delivery receipts, etc.)
    if not message.body:
        log.debug("webhook.empty_body", channel=channel, sender=message.sender)
        return

    session_store = request.app.state.session_store
    embedder = request.app.state.embedder
    vector_store = request.app.state.vector_store
    llm_svc = LLMService()

    # Get/update session
    await session_store.add_turn(channel, message.sender, "user", message.body)
    session = await session_store.get_session(channel, message.sender)

    pipeline = RAGPipeline(embedder, vector_store, llm_svc)
    result = await pipeline.run(message, session)

    # Save assistant turn
    await session_store.add_turn(channel, message.sender, "assistant", result.answer)

    # Format & send
    outgoing = adapter.format_response(result, message.sender)
    await adapter.send(outgoing)


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    form = await request.form()
    payload = dict(form)

    log.info("webhook.whatsapp_received", from_=payload.get("From"), body_preview=payload.get("Body", "")[:60])

    background_tasks.add_task(_handle_message, Channel.WHATSAPP, payload, request)

    # Twilio needs 200 OK immediately; we process async
    return Response(content="", media_type="text/xml", status_code=200)


@router.post("/sms")
async def sms_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    form = await request.form()
    payload = dict(form)

    log.info("webhook.sms_received", from_=payload.get("From"), body_preview=payload.get("Body", "")[:60])

    background_tasks.add_task(_handle_message, Channel.SMS, payload, request)

    return Response(content="", media_type="text/xml", status_code=200)
