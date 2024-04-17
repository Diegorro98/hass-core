"""Stellantis integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import CONF_BRAND, DOMAIN, Brand
from .coordinator import StellantisUpdateCoordinator
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


@dataclass
class HomeAssistantStellantisData:
    """Spotify data stored in the Home Assistant data object."""

    coordinator: StellantisUpdateCoordinator
    session: OAuth2Session


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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = HomeAssistantStellantisData(
        coordinator,
        oauth_session,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up vehicles which are not assigned to the account anymore
    vehicles = {(DOMAIN, v.vin) for v in coordinator.vehicles_data}
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry_id=entry.entry_id
    )

    for device in device_entries:
        if not device.identifiers.intersection(vehicles):
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    implementation = StellantisOauth2Implementation(
        hass, entry.domain, Brand(entry.data[CONF_BRAND])
    )
    oauth_session = StellantisOAuth2Session(hass, entry, implementation)

    await oauth_session.async_revoke_token()
