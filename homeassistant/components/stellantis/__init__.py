"""Stellantis integration."""

import contextlib
from json import JSONDecodeError

import aiohttp
from stellantis.client import Client as StellantisClient
from stellantis.model.error import StellantisError

from homeassistant.components.webhook import async_unregister as webhook_unregister
from homeassistant.const import CONF_COUNTRY, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import AsyncConfigEntryAuth
from .const import CONF_BRAND, DOMAIN, Brand
from .coordinator import (
    StellantisConfigEntry,
    StellantisCoordinator,
    StellantisRuntimeData,
)
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session
from .services import async_setup_hass_services
from .webhook import async_setup_webhook

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
    entry.runtime_data = StellantisRuntimeData(
        stellantis_client, StellantisCoordinator(hass, entry)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await entry.runtime_data.coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(entry.domain, {})
    await async_setup_webhook(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: StellantisConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.runtime_data.callback_id:
        with contextlib.suppress(StellantisError):
            await entry.runtime_data.client.delete_user_remote(
                entry.runtime_data.callback_id
            )

    if CONF_WEBHOOK_ID in entry.data:
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: StellantisConfigEntry) -> None:
    """Handle removal of an entry."""
    implementation = StellantisOauth2Implementation(
        hass, entry.domain, Brand(entry.data[CONF_BRAND]), entry.data[CONF_COUNTRY]
    )
    with contextlib.suppress(
        aiohttp.ClientResponseError, aiohttp.ClientError, JSONDecodeError
    ):
        await implementation.async_revoke_token(
            await implementation.async_refresh_token(entry.data["token"])
        )
