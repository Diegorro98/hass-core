"""Stellantis integration."""

from asyncio import timeout
from dataclasses import dataclass
from http import HTTPStatus

from homeassistant.components import cloud
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import ConfigType

from .const import CONF_BRAND, CONF_CALLBACK_ID, DOMAIN, LOGGER, Brand
from .coordinator import StellantisUpdateCoordinator
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


@dataclass
class HomeAssistantStellantisData:
    """Spotify data stored in the Home Assistant data object."""

    coordinator: StellantisUpdateCoordinator
    session: OAuth2Session


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Stellantis component."""
    await async_setup_hass_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stellantis from a config entry."""
    implementation = StellantisOauth2Implementation(
        hass, entry.domain, Brand(entry.data[CONF_BRAND])
    )

    oauth_session = StellantisOAuth2Session(hass, entry, implementation)

    coordinator = StellantisUpdateCoordinator(
        hass, implementation, oauth_session, entry
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(entry.domain, {})
    hass.data[entry.domain][entry.entry_id] = HomeAssistantStellantisData(
        coordinator,
        oauth_session,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up vehicles which are not assigned to the account anymore
    vehicles = {(entry.domain, v.vin) for v in coordinator.vehicles_data}
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry_id=entry.entry_id
    )

    for device in device_entries:
        if not device.identifiers.intersection(vehicles):
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )

    await async_ensure_reusable_callback_created(hass, entry, oauth_session)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[entry.domain].pop(entry.entry_id)
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    implementation = StellantisOauth2Implementation(
        hass, entry.domain, Brand(entry.data[CONF_BRAND])
    )
    oauth_session = StellantisOAuth2Session(hass, entry, implementation)

    await oauth_session.async_request_to_path(
        "DELETE",
        "/user/callbacks/" + entry.data[CONF_CALLBACK_ID],
    )
    await oauth_session.async_revoke_token()

    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])


async def async_ensure_reusable_callback_created(
    hass: HomeAssistant, entry: ConfigEntry, session: StellantisOAuth2Session
) -> None:
    """Get or create a callback on Stellantis server."""
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    if cloud.async_active_subscription(hass) and cloud.async_is_connected(hass):
        webhook_url = await cloud.async_get_or_create_cloudhook(hass, webhook_id)
    else:
        try:
            webhook_url = (
                f"{get_url(hass, allow_internal=False)}/api/webhook/{webhook_id}"
            )
        except NoURLAvailableError:
            LOGGER.warning(
                "No external URL available, services and controls will not work as they require an url for the callbacks: %s",
            )
            return
    webhook_register(hass, entry.domain, entry.title, webhook_id, handle_webhook)

    if CONF_CALLBACK_ID in entry.data:
        callback_id = entry.data[CONF_CALLBACK_ID]
        async with timeout(10):
            response = await session.async_request_to_path(
                "GET",
                "/user/callbacks/" + callback_id,
            )
        if response.status == HTTPStatus.OK:
            json = await response.json()
            if (
                json["subscribe"]["callback"]["webhook"]["target"] != webhook_url
                or "Remote" not in json["subscribe"]["type"]
            ):
                async with timeout(10):
                    response = await session.async_request_to_path(
                        "PUT",
                        "/user/callbacks/" + callback_id,
                        json=create_callback_data(webhook_url),
                    )
            return

        if response.status != HTTPStatus.NOT_FOUND:
            LOGGER.error(
                "Failed to get callback with id %s, some functionalities will be limited",
                callback_id,
            )
            LOGGER.debug(
                "Status: %i Response: %s", response.status, await response.json()
            )
            return

    async with timeout(10):
        response = await session.async_request_to_path(
            "POST",
            "/user/callbacks",
            json=create_callback_data(webhook_url),
        )
        if response.status == HTTPStatus.ACCEPTED:
            json = await response.json()
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_CALLBACK_ID: json["callbackId"]},
            )
            LOGGER.debug("Callback created with id %s", json["callbackId"])
        else:
            LOGGER.error(
                "Failed to create callback, some functionalities will be limited"
            )
            LOGGER.debug(
                "Status: %i Response: %s", response.status, await response.json()
            )


def create_callback_data(webhook_url: str) -> dict:
    """Create callback data."""
    return {
        "label": "Home Assistant callback",
        "type": ["Remote"],
        "callback": {
            "webhook": {
                "name": "Home Assistant webhook",
                "target": webhook_url,
                "attributes": [
                    {"type": "Header", "key": "empty_but_required", "value": "."}
                ],
            }
        },
    }
