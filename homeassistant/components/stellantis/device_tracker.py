"""Stellantis device tracker platform."""

from dataclasses import asdict, dataclass

from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StellantisConfigEntry
from .entity import StellantisBaseEntity, StellantisEntityDescription


@dataclass(frozen=True, kw_only=True)
class StellantisTrackerEntityDescription(
    StellantisEntityDescription, TrackerEntityDescription
):
    """Describes a Stellantis tracker entity."""


DEVICE_TRACKER_ENTITY_DESCRIPTION = StellantisTrackerEntityDescription(
    key="device_tracker", name="", value_fn=lambda _: None
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updates from the coordinator."""
        vehicle_status = self.vehicle_status
        self._attr_longitude = None
        self._attr_latitude = None
        self._attr_extra_state_attributes = {}
        if last_position := vehicle_status.last_position:
            coordinates = last_position.geometry.coordinates
            if len(coordinates) >= 2:
                self._attr_longitude = coordinates[0]
                self._attr_latitude = coordinates[1]
                if len(coordinates) >= 3:
                    self._attr_extra_state_attributes["altitude"] = coordinates[2]
            self._attr_extra_state_attributes.update(asdict(last_position.properties))
            self._attr_available = True
        else:
            self._attr_available = False
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._attr_available
