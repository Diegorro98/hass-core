"""Stellantis device tracker platform."""

from collections.abc import Mapping
import contextlib
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .const import ATTR_ALTITUDE, ATTR_HEADING, ATTR_SIGNAL_QUALITY, DOMAIN
from .entity import StellantisBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis device tracker."""
    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StellantisTrackerEntity(
            data.coordinator,
            vehicle_data,
            EntityDescription(
                key="device_tracker",
                name="",
                icon="mdi:car-arrow-right",
            ),
        )
        for vehicle_data in data.coordinator.vehicles_data
    )


class StellantisTrackerEntity(StellantisBaseEntity, TrackerEntity):
    """Representation of a Stellantis vehicle tracker entity."""

    source_type = SourceType.GPS

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the vehicle."""
        return self.get_from_vehicle_status("$.lastPosition.geometry.coordinates[0]")

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the vehicle."""
        return self.get_from_vehicle_status("$.lastPosition.geometry.coordinates[1]")

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return device specific attributes."""
        attrs = {}
        with contextlib.suppress(KeyError, IndexError):
            attrs[ATTR_ALTITUDE] = self.get_from_vehicle_status(
                "$.lastPosition.geometry.coordinates[2]"
            )
        with contextlib.suppress(KeyError):
            attrs[ATTR_HEADING] = self.get_from_vehicle_status(
                "$.lastPosition.properties.heading"
            )
        with contextlib.suppress(KeyError):
            attrs[ATTR_SIGNAL_QUALITY] = self.get_from_vehicle_status(
                "$.lastPosition.properties.signalQuality"
            )
        return attrs
