"""Stellantis device tracker platform."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StellantisConfigEntry
from .entity import StellantisBaseEntity, StellantisEntityDescription


@dataclass(frozen=True, kw_only=True)
class StellantisTrackerEntityDescription(
    StellantisEntityDescription, TrackerEntityDescription
):
    """Describes a Stellantis tracker entity."""


DEVICE_TRACKER_ENTITY_DESCRIPTION = StellantisTrackerEntityDescription(
    key="device_tracker", value_fn=lambda _: None
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis device tracker."""
    async_add_entities(
        StellantisTrackerEntity(
            vehicle_coordinator,
            DEVICE_TRACKER_ENTITY_DESCRIPTION,
        )
        for vehicle_coordinator in entry.runtime_data
    )


class StellantisTrackerEntity(StellantisBaseEntity, TrackerEntity):
    """Representation of a Stellantis vehicle tracker entity."""

    entity_description: StellantisTrackerEntityDescription

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the vehicle."""
        if self.vehicle_status.last_position:
            return self.vehicle_status.last_position.geometry.coordinates[0]
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the vehicle."""
        if self.vehicle_status.last_position:
            return self.vehicle_status.last_position.geometry.coordinates[1]
        return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return device specific attributes."""
        if self.vehicle_status.last_position:
            return {
                "altitude": self.vehicle_status.last_position.geometry.coordinates[2],
                "heading": self.vehicle_status.last_position.properties.heading,
                "signal_quality": self.vehicle_status.last_position.properties.signal_quality,
                "created_at": self.vehicle_status.last_position.properties.created_at,
            }
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.vehicle_status.last_position is not None
