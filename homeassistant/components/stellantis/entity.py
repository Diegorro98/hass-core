"""Stellantis entity base class."""

from typing import Any

from jsonpath import jsonpath

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StellantisUpdateCoordinator, VehicleData


class StellantisBaseEntity(CoordinatorEntity[StellantisUpdateCoordinator], Entity):
    """Common base for Stellantis entities."""

    coordinator: StellantisUpdateCoordinator

    def __init__(
        self,
        coordinator: StellantisUpdateCoordinator,
        vehicle: VehicleData,
        description: EntityDescription,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self.vehicle = vehicle
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.vehicle.vin)},
            manufacturer=self.vehicle.brand,
            model=self.vehicle.label,
            name=f"{self.vehicle.brand} {self.vehicle.label}",
            serial_number=self.vehicle.vin,
        )
        self.entity_description = description

    def get_from_vehicle_status(self, value_path: str) -> Any:
        """Return the vehicle status."""
        try:
            if matches := jsonpath(
                self.coordinator.vehicles_status[self.vehicle.vin], value_path
            ):
                return matches[0]
        except KeyError:
            pass
        return None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
