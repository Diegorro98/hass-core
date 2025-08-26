"""Stellantis integration."""

import asyncio
import contextlib
from http import HTTPStatus
from typing import cast

import aiohttp
from stellantis.client import Client as StellantisClient
from stellantis.model import (
    Attribute,
    AttributeType,
    Callback,
    CallbackSubscribe,
    CallbackType,
    VehicleExtensionType,
    Webhook,
)
from stellantis.model.error import StellantisApiError, StellantisError

from homeassistant.components import cloud
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.const import CONF_COUNTRY, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import ConfigType

from .api import AsyncConfigEntryAuth
from .const import (
    CONF_BRAND,
    CONF_CALLBACK_ID,
    CONF_CLOUDHOOK_URL,
    DOMAIN,
    LOGGER,
    Brand,
)
from .coordinator import StellantisConfigEntry, StellantisVehicleCoordinator
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session
from .services import async_setup_hass_services
from .webhook import handle_webhook

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORM_SCHEMA = cv.platform_only_config_schema(DOMAIN)

_CLOUD_HOOK_LOCK = asyncio.Lock()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Stellantis component."""
    await async_setup_hass_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StellantisConfigEntry) -> bool:
    """Set up Stellantis from a config entry."""
    implementation = StellantisOauth2Implementation(
        hass, entry.domain, Brand(entry.data[CONF_BRAND]), entry.data[CONF_COUNTRY]
    )

    oauth_session = StellantisOAuth2Session(hass, entry, implementation)

    config_entry_auth = AsyncConfigEntryAuth(hass, oauth_session)
    try:
        await config_entry_auth.async_get_access_token()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    stellantis_client = StellantisClient(config_entry_auth)

    entry.runtime_data = []
    vehicles_response = await stellantis_client.get_vehicles_by_device(
        extension=[VehicleExtensionType.BRANDING]
    )
    if vehicles_response.embedded and (vehicles := vehicles_response.embedded.vehicles):
        for vehicle in vehicles:
            coordinator = StellantisVehicleCoordinator(
                hass, entry, stellantis_client, vehicle
            )
            await coordinator.async_config_entry_first_refresh()
            entry.runtime_data.append(coordinator)

    hass.data.setdefault(entry.domain, {})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up vehicles which are not assigned to the account anymore
    vehicles_identifiers = {
        (entry.domain, coordinator.vehicle.vin)
        for coordinator in entry.runtime_data
        if coordinator.vehicle.vin is not None
    }
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry_id=entry.entry_id
    )

    for device in device_entries:
        if not device.identifiers.intersection(vehicles_identifiers):
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )

    await async_ensure_reusable_callback_created(hass, entry, stellantis_client)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: StellantisConfigEntry) -> bool:
    """Unload a config entry."""
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: StellantisConfigEntry) -> None:
    """Handle removal of an entry."""
    if entry.runtime_data:
        client = entry.runtime_data[0].client
        with contextlib.suppress(StellantisError):
            await client.delete_user_remote(entry.data[CONF_CALLBACK_ID])

    implementation = StellantisOauth2Implementation(
        hass, entry.domain, Brand(entry.data[CONF_BRAND]), entry.data[CONF_COUNTRY]
    )
    oauth_session = StellantisOAuth2Session(hass, entry, implementation)
    await oauth_session.async_revoke_token()

    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])


async def async_ensure_reusable_callback_created(
    hass: HomeAssistant, entry: StellantisConfigEntry, client: StellantisClient
) -> None:
    """Get or create a callback on Stellantis server."""
    webhook_id = cast(str, entry.data[CONF_WEBHOOK_ID])
    webhook_register(hass, entry.domain, entry.title, webhook_id, handle_webhook)
    webhook_url: str | None = None

    async def async_create_cloud_hook_url() -> str:
        async with _CLOUD_HOOK_LOCK:
            cloudhook_url = await cloud.async_get_or_create_cloudhook(hass, webhook_id)
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_CLOUDHOOK_URL: webhook_url}
            )
            return cloudhook_url

    if cloud.async_is_logged_in(hass):
        if (
            CONF_CLOUDHOOK_URL not in entry.data
            and cloud.async_active_subscription(hass)
            and cloud.async_is_connected(hass)
        ):
            async with _CLOUD_HOOK_LOCK:
                webhook_url = await async_create_cloud_hook_url()
    else:
        if CONF_CLOUDHOOK_URL in entry.data:
            data = dict(entry.data)
            data.pop(CONF_CLOUDHOOK_URL)
            hass.config_entries.async_update_entry(entry, data=data)
        try:
            webhook_url = (
                get_url(hass, allow_internal=False) + "/api/webhook/" + webhook_id
            )
        except NoURLAvailableError:
            LOGGER.warning(
                "No external URL available, services and controls will not work as they require an url for the callbacks",
            )
            return

    async def async_create_or_update_callback(webhook_url: str) -> None:
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
                    create_callback_data(webhook_url),
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

        try:
            callback = await client.set_user_vehicle_remote(
                create_callback_data(webhook_url)
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

    if webhook_url:
        await async_create_or_update_callback(webhook_url)

    async def async_manage_cloudhook(state: cloud.CloudConnectionState) -> None:
        if (
            state is cloud.CloudConnectionState.CLOUD_CONNECTED
            and CONF_CLOUDHOOK_URL not in entry.data
        ):
            cloudhook_url = await async_create_cloud_hook_url()
            await async_create_or_update_callback(cloudhook_url)

    entry.async_on_unload(
        cloud.async_listen_connection_change(hass, async_manage_cloudhook)
    )


def create_callback_data(webhook_url: str) -> CallbackSubscribe:
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
