"""Stellantis entity base classes."""

from abc import abstractmethod
from asyncio import timeout
from typing import Any

from jsonpath import jsonpath

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import (
    Entity,
    EntityDescription,
    ToggleEntity,
    ToggleEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import StellantisVehicle
from .const import (
    ATTR_EVENT_TYPE,
    ATTR_FAILURE_CAUSE,
    ATTR_REMOTE_ACTION_ID,
    ATTR_STATUS,
    CONF_CALLBACK_ID,
    DOMAIN,
    LOGGER,
    EventStatusType,
    RemoteDoneEventStatus,
)
from .coordinator import StellantisUpdateCoordinator
from .webhook import StellantisCallbackEvent


class StellantisBaseEntity(CoordinatorEntity[StellantisUpdateCoordinator], Entity):
    """Common base for Stellantis entities."""

    coordinator: StellantisUpdateCoordinator

    def __init__(
        self,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        description: EntityDescription,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self.vehicle = vehicle
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{vehicle.details.vin}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.vehicle.details.vin)},
            manufacturer=self.vehicle.details.brand,
            model=f"{self.vehicle.details.label} {self.vehicle.details.motorization}",
            name=f"{self.vehicle.details.brand} {self.vehicle.details.label}",
            serial_number=self.vehicle.details.vin,
        )
        self.entity_description = description

    def get_from_vehicle_status(self, value_path: str) -> Any:
        """Return the vehicle status."""
        if matches := jsonpath(self.vehicle.status, value_path):
            return matches[0]
        raise KeyError(value_path)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class StellantisBaseActionableEntity(StellantisBaseEntity):
    """Common base for Stellantis entities that can call remote actions."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        description: EntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, vehicle, description)
        self.hass = hass
        self.entry = entry

    @abstractmethod
    def on_remote_action_success(self, state_if_success: Any):
        """Handle the success of a remote action."""
        raise NotImplementedError

    async def async_call_remote_action(
        self, request_body: dict[str, Any], state_if_success: Any, logger_action: str
    ) -> None:
        """Call a remote action and handle the response."""
        async with timeout(10):
            response_data = await self.coordinator.api.async_send_remote_action(
                self.vehicle.details.id,
                self.entry.data[CONF_CALLBACK_ID],
                request_body,
            )

        if ATTR_REMOTE_ACTION_ID not in response_data:
            LOGGER.warning(
                f"The remote action to {logger_action} will not be tracked as the remote action ID is missing from the API response"
            )

        try:
            async with timeout(10):
                while True:
                    with StellantisCallbackEvent(
                        self.hass, response_data[ATTR_REMOTE_ACTION_ID]
                    ) as callback_event:
                        event_status = await callback_event
                        match event_status[ATTR_EVENT_TYPE]:
                            case EventStatusType.PENDING:
                                continue
                            case EventStatusType.DONE:
                                match event_status[ATTR_STATUS]:
                                    case RemoteDoneEventStatus.FAILED:
                                        raise HomeAssistantError(
                                            f"Remote action failed. Cause: {event_status.get(ATTR_FAILURE_CAUSE, "Not specified")}"
                                        )
                                self.on_remote_action_success(state_if_success)
                        break
        except TimeoutError:
            LOGGER.warning(
                f"Confirmation of the remote action to {logger_action} was not received in time"
            )


class StellantisBaseToggleEntity(StellantisBaseActionableEntity, ToggleEntity):
    """Common base for Stellantis entities that can be toggled."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        description: ToggleEntityDescription,
        entry: ConfigEntry,
        value_path: str | None,
        request_body_on: dict[str, Any],
        request_body_off: dict[str, Any],
        logger_action_on: str,
        logger_action_off: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(hass, coordinator, vehicle, description, entry)
        self.value_path = value_path
        self.request_body_on = request_body_on
        self.request_body_off = request_body_off
        self.logger_action_on = logger_action_on
        self.logger_action_off = logger_action_off

    @property
    def status_value(self):
        """Return the state reported from the API."""
        return self.get_from_vehicle_status(self.value_path)

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

    def on_remote_action_success(self, state_if_success: Any):
        """Handle the success of a remote action."""
        self._attr_is_on = state_if_success
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return true if the vehicle is turned off."""
        if self.get_from_vehicle_status("$.ignition.type") == "Stop":
            if not self.value_path:
                return super().available
            try:
                _ = self.status_value
            except KeyError:
                return False
            return super().available
        return False
