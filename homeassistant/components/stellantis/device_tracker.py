"""Stellantis device tracker platform."""

from collections.abc import Mapping
import contextlib
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
            TrackerEntityDescription(
                key="device_tracker",
                name="",
                icon="mdi:car-arrow-right",
            ),
        )
        for vehicle_data in data.coordinator.data
    )


class StellantisTrackerEntity(StellantisBaseEntity, TrackerEntity):
    """Representation of a Stellantis vehicle tracker entity."""

    entity_description: TrackerEntityDescription
    source_type = SourceType.GPS

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the vehicle."""
        try:
            return self.get_from_vehicle_status(
                "$.lastPosition.geometry.coordinates[0]"
            )
        except KeyError:
            return None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the vehicle."""
        try:
            return self.get_from_vehicle_status(
                "$.lastPosition.geometry.coordinates[1]"
            )
        except KeyError:
            return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return device specific attributes."""
        attrs = {}
        for attr, path in (
            (ATTR_ALTITUDE, "geometry.coordinates[2]"),
            (ATTR_HEADING, "properties.heading"),
            (ATTR_SIGNAL_QUALITY, "properties.signalQuality"),
        ):
            with contextlib.suppress(KeyError, IndexError):
                attrs[attr] = self.get_from_vehicle_status("$.lastPosition." + path)
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        try:
            self.get_from_vehicle_status("$.lastPosition")
            return super().available
        except KeyError:
            return False
