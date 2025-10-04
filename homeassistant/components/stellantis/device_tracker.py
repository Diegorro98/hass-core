"""Stellantis device tracker platform."""

from dataclasses import asdict, dataclass

from stellantis.model import OnboardCapabilitiesEnum

from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity,
    TrackerEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import StellantisConfigEntry
from .entity import StellantisBaseEntity, StellantisEntityDescription

PARALLEL_UPDATES = 0


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
            onboard_capabilities_data is None,
        )
        for vehicle_coordinator in entry.runtime_data.vehicle_coordinators
        if (
            onboard_capabilities_data := (
                vehicle_coordinator.vehicle.embedded.extension.onboard_capabilities.data
                if vehicle_coordinator.vehicle.embedded
                and vehicle_coordinator.vehicle.embedded.extension
                and vehicle_coordinator.vehicle.embedded.extension.onboard_capabilities
                else None
            )
        )
        is None
        or OnboardCapabilitiesEnum.DATA_POSITION in onboard_capabilities_data
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
            if not self._attr_available:
                LOGGER.info(
                    "The entity %s is now available because the last position can be retrieved",
                    self.entity_id,
                )
            self._attr_available = True
        else:
            if self._attr_available:
                LOGGER.info(
                    "The entity %s is no longer available because the last position cannot be retrieved",
                    self.entity_id,
                )
            self._attr_available = False
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._attr_available
