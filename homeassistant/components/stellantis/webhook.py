"""Webhook handler for Stellantis integration."""

from asyncio import Future
from http import HTTPStatus
from json.decoder import JSONDecodeError
from typing import Any

from aiohttp.web import Request, Response
from mashumaro.exceptions import (
    BadDialect,
    BadHookSignature,
    ExtraKeysError,
    InvalidFieldValue,
    MissingDiscriminatorError,
    MissingField,
    SuitableVariantNotFoundError,
    ThirdPartyModuleNotFoundError,
    UnresolvedTypeReferenceError,
    UnserializableDataError,
    UnserializableField,
    UnsupportedDeserializationEngine,
    UnsupportedSerializationEngine,
)
from stellantis.model import Message, RemoteEventStatus, RemoteEventType

from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> Response:
    """Handle webhook callback."""
    try:
        data = Message.from_dict(await request.json())
    except (
        JSONDecodeError,
        MissingField,
        ExtraKeysError,
        UnserializableDataError,
        UnserializableField,
        UnsupportedSerializationEngine,
        UnsupportedDeserializationEngine,
        InvalidFieldValue,
        MissingDiscriminatorError,
        SuitableVariantNotFoundError,
        BadHookSignature,
        ThirdPartyModuleNotFoundError,
        UnresolvedTypeReferenceError,
        BadDialect,
    ):
        LOGGER.exception("Received invalid webhook payload: %s", await request.text())
        return Response(status=HTTPStatus.BAD_REQUEST)

    if not (remote_event := data.remote_event) or not (
        event_status := remote_event.event_status
    ):
        return Response(status=HTTPStatus.BAD_REQUEST)
    if event_status.type == RemoteEventType.DONE:
        handlers: dict[str, StellantisCallbackEvent] = hass.data.setdefault(DOMAIN, {})
        remote_action_id = data.remote_event.remote_action_id
        if remote_action_id in handlers:
            callback_event = handlers[remote_action_id]
            callback_event.set_result(event_status)
    LOGGER.debug("Received webhook payload: %s", await request.text())
    return Response(status=HTTPStatus.OK)


class StellantisCallbackEvent(Future[RemoteEventStatus]):
    """Future for callback events."""

    def __init__(self, hass: HomeAssistant, remote_action_id: str) -> None:
        """Initialize the future."""
        super().__init__()
        self.hass = hass
        self.remote_action_id = remote_action_id

    def __enter__(self) -> "StellantisCallbackEvent":
        """Enter the context manager."""
        handlers: dict[str, Any] = self.hass.data.setdefault(DOMAIN, {})
        handlers[self.remote_action_id] = self
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exit the context manager."""
        handlers: dict[str, dict[str, Any]] = self.hass.data.setdefault(DOMAIN, {})
        handlers.pop(self.remote_action_id, None)
