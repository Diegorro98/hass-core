"""Stellantis integration."""

from asyncio import timeout
from http import HTTPStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import API_ENDPOINT, CONF_BRAND, DOMAIN, Brand
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session

PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stellantis from a config entry."""
    implementation = StellantisOauth2Implementation(
        hass, entry.domain, Brand(entry.data[CONF_BRAND])
    )

    oauth_session = StellantisOAuth2Session(hass, entry, implementation)

    params = {
        "extension": [
            # "onboardCapabilities", Causes HTTP 500 error
            "branding",
            "pictures",
        ],
    }
    async with timeout(10):
        response = await oauth_session.async_request(
            "GET",
            API_ENDPOINT + "/user/vehicles",
            params=params,
        )

    if response.status != HTTPStatus.OK:
        result = await response.json()
        return False

    result = await response.json()
    vehicles = result["_embedded"]["vehicles"]
    while "next" in result["_links"]:
        next_page = result["_links"]["next"]["href"]
        async with timeout(10):
            response = await oauth_session.async_request(
                "POST", next_page, params=params
            )
            if response.status == HTTPStatus.OK:
                result = await response.json()
                vehicles += result["_embedded"]["vehicles"]
            else:
                break

    device_registry = dr.async_get(hass)

    for vehicle in vehicles:
        branding = vehicle["_embedded"]["extension"]["branding"]
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, vehicle["id"])},
            manufacturer=branding["brand"],
            # model=branding["label"], TODO waiting for server fix
            model="unknown",
            # name=f'{branding["brand"]} {vehicle["label"]}', TODO waiting for server fix
            name=f'{branding["brand"]} {vehicle["vin"]}',
            serial_number=vehicle["vin"],
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
