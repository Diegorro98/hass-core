"""Stellantis entity base class."""

from asyncio import timeout
from typing import Any

from jsonpath import jsonpath

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription, ToggleEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_FAILURE_CAUSE,
    ATTR_REMOTE_ACTION_ID,
    ATTR_STATUS,
    CONF_CALLBACK_ID,
    DOMAIN,
    LOGGER,
)
from .coordinator import StellantisUpdateCoordinator, VehicleData
from .webhook import StellantisCallbackEvent


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


class StellantisBaseToggleEntity(StellantisBaseEntity, ToggleEntity):
    """Common base for Stellantis entities that can be toggled."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: VehicleData,
        description: EntityDescription,
        entry: ConfigEntry,
        request_body_on: dict[str, Any],
        request_body_off: dict[str, Any],
        logger_action_on: str,
        logger_action_off: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, vehicle, description)
        self.hass = hass
        self.entry = entry
        self.request_body_on = request_body_on
        self.request_body_off = request_body_off
        self.logger_action_on = logger_action_on
        self.logger_action_off = logger_action_off

    async def async_call_remote_action(
        self, request_body: dict[str, Any], state_if_success: bool, logger_action: str
    ) -> None:
        """Call a remote action and handle the response."""
        async with timeout(10):
            response_data = await self.coordinator.api.async_send_remote_action(
                self.vehicle,
                self.entry.data[CONF_CALLBACK_ID],
                request_body,
            )

        if ATTR_REMOTE_ACTION_ID not in response_data:
            LOGGER.warning(
                f"The remote action to {logger_action} will not be tracked as the remote action ID is missing from the API response"
            )

        with StellantisCallbackEvent(
            self.hass, response_data[ATTR_REMOTE_ACTION_ID]
        ) as callback_event:
            try:
                async with timeout(10):
                    event_status = await callback_event
                    if event_status[ATTR_STATUS] == "Failed":
                        raise HomeAssistantError(
                            f"Remote action failed. Cause: {event_status[ATTR_FAILURE_CAUSE]}"
                        )
                    if self._attr_assumed_state:
                        self._attr_is_on = state_if_success
            except TimeoutError:
                LOGGER.warning(
                    f"Confirmation of the remote action to {logger_action} was not received in time"
                )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send a remote action to turn on something."""
        await self.async_call_remote_action(
            self.request_body_on, True, self.logger_action_on
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send a remote action to turn off something."""
        await self.async_call_remote_action(
            self.request_body_off, False, self.logger_action_off
        )

    @property
    def available(self) -> bool:
        """Return true if the vehicle is turned off."""
        return self.get_from_vehicle_status("$.ignition.type") == "Stop"
