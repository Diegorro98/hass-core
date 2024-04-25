"""Webhook handler for Stellantis integration."""

from asyncio import Future
from http import HTTPStatus
from typing import Any

from aiohttp.web import Request, Response
import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_EVENT_STATUS,
    ATTR_EVENT_TYPE,
    ATTR_FAILURE_CAUSE,
    ATTR_REMOTE_ACTION_ID,
    ATTR_REMOTE_EVENT,
    ATTR_STATUS,
    DOMAIN,
    LOGGER,
)

WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_REMOTE_EVENT): vol.Schema(
            {
                vol.Required(ATTR_REMOTE_ACTION_ID): cv.string,
                vol.Required(ATTR_EVENT_STATUS): vol.Schema(
                    {
                        vol.Required(ATTR_EVENT_TYPE): vol.Any("Pending", "Done"),
                        vol.Required(ATTR_STATUS): vol.Any(
                            "Success", "AlreadyDone", "Failed"
                        ),
                        # vol.Required(ATTR_STATUS): vol.Schema(
                        #     {
                        #         vol.Optional(ATTR_REMOTE_DONE_EVENT_STATUS): vol.Any("Success", "AlreadyDone", "Failed"),
                        #         vol.Optional(ATTR_REMOTE_PENDING_EVENT_STATUS): cv.string,
                        #     }
                        # ),
                        vol.Optional(ATTR_FAILURE_CAUSE): cv.string,
                    }
                ),
            },
            extra=vol.ALLOW_EXTRA,
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> Response:
    """Handle webhook callback."""
    data = await request.json()
    try:
        data = WEBHOOK_SCHEMA(data)
    except vol.Invalid as ex:
        err = vol.humanize.humanize_error(data, ex)
        LOGGER.error("Received invalid webhook payload: %s", err)
        return Response(status=HTTPStatus.BAD_REQUEST)

    event_status = data[ATTR_REMOTE_EVENT][ATTR_EVENT_STATUS]
    if event_status[ATTR_EVENT_TYPE] == "Done":
        handlers: dict[str, Any] = hass.data.setdefault(DOMAIN, {})
        remote_action_id = data[ATTR_REMOTE_EVENT][ATTR_REMOTE_ACTION_ID]
        if remote_action_id in handlers:
            callback_event: StellantisCallbackEvent = handlers[remote_action_id]
            callback_event.set_result(event_status)
    LOGGER.debug("Received webhook payload: %s", data)
    return Response(status=HTTPStatus.OK)


class StellantisCallbackEvent(Future):
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
