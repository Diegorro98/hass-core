"""Webhook handler for Stellantis integration."""

from asyncio import Future
import contextlib
from http import HTTPStatus
from json.decoder import JSONDecodeError
import secrets
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
from stellantis.model import (
    Attribute,
    AttributeType,
    Callback,
    CallbackSubscribe,
    CallbackType,
    Message,
    RemoteEventStatus,
    RemoteEventType,
    Webhook,
)
from stellantis.model.error import StellantisError

from homeassistant.components import cloud
from homeassistant.components.webhook import (
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.helpers.start import async_at_started

from .const import CONF_CLOUDHOOK_URL, DOMAIN, LOGGER
from .coordinator import StellantisConfigEntry


async def _handle_webhook(
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
    else:
        if (
            data.remote_event
            and (event_status := data.remote_event.event_status)
            and event_status.type == RemoteEventType.DONE
        ):
            handlers: dict[str, StellantisCallbackEvent] = hass.data.get(DOMAIN, {})
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


async def async_setup_webhook(
    hass: HomeAssistant, entry: StellantisConfigEntry
) -> None:
    """Set up the webhook for the Stellantis integration."""

    stellantis_client = entry.runtime_data.client

    async def unregister_webhook(
        _: Any,
    ) -> None:
        LOGGER.debug("Unregister webhook (%s)", entry.data[CONF_WEBHOOK_ID])
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        if entry.runtime_data.callback_id:
            try:
                await stellantis_client.delete_user_remote(
                    entry.runtime_data.callback_id
                )
            except StellantisError:
                LOGGER.exception(
                    "Error while trying to drop webhook %s at callback %s",
                    entry.data[CONF_WEBHOOK_ID],
                    entry.runtime_data.callback_id,
                )

    async def register_webhook(
        _: Any,
    ) -> None:
        if CONF_WEBHOOK_ID not in entry.data:
            data = {**entry.data, CONF_WEBHOOK_ID: secrets.token_hex()}
            hass.config_entries.async_update_entry(entry, data=data)

        if cloud.async_active_subscription(hass) and cloud.async_is_connected(hass):
            webhook_url = await _async_cloudhook_generate_url(hass, entry)
        else:
            await _async_delete_cloudhook(hass, entry)
            try:
                webhook_url = webhook_generate_url(
                    hass, entry.data[CONF_WEBHOOK_ID], False, True, False
                )
            except NoURLAvailableError as err:
                LOGGER.debug("Error generating webhook URL", exc_info=err)
                return

        with contextlib.suppress(ValueError):
            webhook_register(
                hass,
                DOMAIN,
                "Stellantis",
                entry.data[CONF_WEBHOOK_ID],
                _handle_webhook,
            )

        try:
            LOGGER.debug("Register Stellantis webhook: %s", webhook_url)
            if entry.runtime_data.callback_id:
                callback = await stellantis_client.set_user_vehicle_remote_by_id(
                    entry.runtime_data.callback_id, _create_callback_data(webhook_url)
                )
            else:
                callback = await stellantis_client.set_user_vehicle_remote(
                    _create_callback_data(webhook_url)
                )
        except StellantisError as err:
            LOGGER.error("Error during webhook registration: %s", err)
            entry.runtime_data.callback_id = None
        else:
            entry.runtime_data.callback_id = callback.callback_id
            entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
            )

    if cloud.async_active_subscription(hass):
        entry.async_on_unload(
            cloud.async_listen_connection_change(hass, register_webhook)
        )
        if cloud.async_is_connected(hass):
            await register_webhook(None)
            return

    entry.async_on_unload(async_at_started(hass, register_webhook))

    return


def _create_callback_data(webhook_url: str) -> CallbackSubscribe:
    """Create callback data."""
    return CallbackSubscribe(
        label="Home Assistant callback",
        type=[CallbackType.REMOTE],
        callback=Callback(
            webhook=Webhook(
                name="Home Assistant webhook",
                target=webhook_url,
                attributes=[
                    Attribute(
                        type=AttributeType.HEADER, key="empty_but_required", value="."
                    )
                ],
            )
        ),
    )


async def _async_cloudhook_generate_url(
    hass: HomeAssistant, entry: StellantisConfigEntry
) -> str:
    """Generate the full URL for a webhook_id."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        webhook_url = await cloud.async_create_cloudhook(
            hass, entry.data[CONF_WEBHOOK_ID]
        )
        data = {**entry.data, CONF_CLOUDHOOK_URL: webhook_url}
        hass.config_entries.async_update_entry(entry, data=data)
        return webhook_url
    return str(entry.data[CONF_CLOUDHOOK_URL])


async def _async_delete_cloudhook(
    hass: HomeAssistant, entry: StellantisConfigEntry
) -> None:
    """Delete the cloudhook for a webhook_id."""
    if CONF_CLOUDHOOK_URL not in entry.data:
        return
    await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
    data = dict(entry.data)
    data.pop(CONF_CLOUDHOOK_URL)
    hass.config_entries.async_update_entry(entry, data=data)
