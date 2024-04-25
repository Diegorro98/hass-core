"""Stellantis switch platform."""

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .const import DOMAIN
from .coordinator import StellantisUpdateCoordinator, VehicleData
from .entity import StellantisBaseToggleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""

    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StellantisLights(
            hass,
            data.coordinator,
            vehicle_data,
            entry,
        )
        for vehicle_data in data.coordinator.vehicles_data
    )


class StellantisLights(StellantisBaseToggleEntity, LightEntity):
    """Representation of Stellantis vehicle lights."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: VehicleData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the vehicle lights."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            LightEntityDescription(
                key="lights",
                translation_key="lights",
            ),
            entry,
            {"lights": {"on": True}},
            {"lights": {"on": False}},
            "turn on the lights",
            "turn off the lights",
        )
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_assumed_state = False
