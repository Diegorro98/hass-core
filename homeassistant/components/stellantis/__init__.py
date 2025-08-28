"""Stellantis integration."""

import contextlib

import aiohttp
from stellantis.client import Client as StellantisClient
from stellantis.model import VehicleExtensionType
from stellantis.model.error import StellantisError

from homeassistant.components.webhook import async_unregister as webhook_unregister
from homeassistant.const import CONF_COUNTRY, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .api import AsyncConfigEntryAuth
from .const import CONF_BRAND, CONF_CALLBACK_ID, DOMAIN, Brand
from .coordinator import StellantisConfigEntry, StellantisVehicleCoordinator
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session
from .services import async_setup_hass_services
from .webhook import async_ensure_reusable_callback_created

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
