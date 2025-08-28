"""Webhook handler for Stellantis integration."""

import asyncio
from asyncio import Future
from http import HTTPStatus
from json.decoder import JSONDecodeError
from typing import Any, cast

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
from stellantis.client import Client as StellantisClient
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
from stellantis.model.error import StellantisApiError

from homeassistant.components import cloud
from homeassistant.components.webhook import async_register as webhook_register
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CONF_CALLBACK_ID, CONF_CLOUDHOOK_URL, DOMAIN, LOGGER
from .coordinator import StellantisConfigEntry

_CLOUD_HOOK_LOCK = asyncio.Lock()


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


async def _async_create_cloud_hook_url(
    hass: HomeAssistant, entry: StellantisConfigEntry, webhook_id: str
) -> str:
    async with _CLOUD_HOOK_LOCK:
        cloudhook_url = await cloud.async_get_or_create_cloudhook(hass, webhook_id)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_CLOUDHOOK_URL: cloudhook_url}
        )
        return cloudhook_url


async def _async_create_or_update_callback(
    webhook_url: str, entry: StellantisConfigEntry, client: StellantisClient
) -> None:
    if CONF_CALLBACK_ID in entry.data:
        callback_id = entry.data[CONF_CALLBACK_ID]
        user_callback = await client.get_user_remote_by_id(
            callback_id,
        )
        if (
            user_callback.subscribe
            and user_callback.subscribe.callback.webhook
            and user_callback.subscribe.callback.webhook.target != webhook_url
            and user_callback.subscribe.type
            and CallbackType.REMOTE in user_callback.subscribe.type
        ):
            return

        try:
            await client.set_user_vehicle_remote_by_id(
                "/user/callbacks/" + callback_id,
                _create_callback_data(webhook_url),
            )
        except StellantisApiError as err:
            if err.code == HTTPStatus.NOT_FOUND:
                LOGGER.info(
                    "Callback with id %s not found, creating a new one",
                    callback_id,
                )
            else:
                LOGGER.exception(
                    "Failed to update callback with id %s, some functionalities will be limited",
                    callback_id,
                )
                return


async def _async_manage_cloudhook(
    hass: HomeAssistant,
    state: cloud.CloudConnectionState,
    entry: StellantisConfigEntry,
    client: StellantisClient,
    webhook_id: str,
) -> None:
    if (
        state is cloud.CloudConnectionState.CLOUD_CONNECTED
        and CONF_CLOUDHOOK_URL not in entry.data
    ):
        cloudhook_url = await _async_create_cloud_hook_url(hass, entry, webhook_id)
        await _async_create_or_update_callback(cloudhook_url, entry, client)


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


async def async_ensure_reusable_callback_created(
    hass: HomeAssistant, entry: StellantisConfigEntry, client: StellantisClient
) -> None:
    """Get or create a callback on Stellantis server."""
    webhook_id = cast(str, entry.data[CONF_WEBHOOK_ID])
    webhook_register(hass, entry.domain, entry.title, webhook_id, _handle_webhook)
    webhook_url: str | None = None
    use_cloudhook = False

    if cloud.async_is_logged_in(hass):
        if (
            CONF_CLOUDHOOK_URL not in entry.data
            and cloud.async_active_subscription(hass)
            and cloud.async_is_connected(hass)
        ):
            async with _CLOUD_HOOK_LOCK:
                webhook_url = await _async_create_cloud_hook_url(
                    hass, entry, webhook_id
                )
                use_cloudhook = True
    elif CONF_CLOUDHOOK_URL in entry.data:
        data = dict(entry.data)
        data.pop(CONF_CLOUDHOOK_URL)
        hass.config_entries.async_update_entry(entry, data=data)

    if webhook_url is None:
        try:
            webhook_url = (
                get_url(hass, allow_internal=False) + "/api/webhook/" + webhook_id
            )
        except NoURLAvailableError:
            LOGGER.debug(
                "No external URL available, the integration will not receive callbacks",
            )
            webhook_url = "none"

        try:
            callback = await client.set_user_vehicle_remote(
                _create_callback_data(webhook_url)
            )
            if callback.callback_id is None:
                LOGGER.error(
                    "Callback created without ID so it cannot be identified, some functionalities will be limited"
                )
                return
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_CALLBACK_ID: callback.callback_id},
            )
            LOGGER.debug("Callback created with id %s", callback.callback_id)
        except StellantisApiError:
            LOGGER.exception(
                "Failed to create callback, some functionalities will be limited"
            )

    if not use_cloudhook:
        await _async_create_or_update_callback(webhook_url, entry, client)

    entry.async_on_unload(
        cloud.async_listen_connection_change(
            hass,
            lambda state: _async_manage_cloudhook(
                hass, state, entry, client, webhook_id
            ),
        )
    )
