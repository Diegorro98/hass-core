"""Stellantis entity base classes."""

from abc import abstractmethod
from asyncio import timeout
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

from stellantis.model import (
    IgnitionType,
    PreconditioningProgram,
    Remote,
    RemoteEventType,
    Status,
    Vehicle,
)
from stellantis.model.error import StellantisError

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import (
    Entity,
    EntityDescription,
    ToggleEntity,
    ToggleEntityDescription,
)
from homeassistant.helpers.typing import StateType, UndefinedType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CALLBACK_ID, DOMAIN, LOGGER, RemoteDoneEventStatus
from .coordinator import StellantisConfigEntry, StellantisVehicleCoordinator
from .webhook import StellantisCallbackEvent

T = TypeVar("T")


@dataclass(frozen=True, kw_only=True)
class StellantisEntityDescription(EntityDescription):
    """Common base description for Stellantis entities that can be toggled."""

    value_fn: Callable[[Status], StateType | UndefinedType]


class StellantisBaseEntity(
    CoordinatorEntity[StellantisVehicleCoordinator],
    Entity,
    cached_properties={"vehicle_status", "status_value"},
):
    """Common base for Stellantis entities."""

    coordinator: StellantisVehicleCoordinator
    entity_description: StellantisEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: StellantisVehicleCoordinator,
        description: StellantisEntityDescription,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, True)
        assert self.vehicle.id
        assert self.vehicle.vin
        self._attr_unique_id = f"{coordinator.vehicle.vin}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.vehicle.vin)},
        )
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updates from the coordinator."""
        self.__dict__.pop("vehicle_status", None)
        self.__dict__.pop("status_value", None)
        super()._handle_coordinator_update()

    @property
    def vehicle(self) -> Vehicle:
        """Get the vehicle details."""
        return self.coordinator.vehicle

    @property
    def vehicle_status(self) -> Status:
        """Get the vehicle status."""
        return self.coordinator.data

    @property
    def status_value(self) -> StateType | UndefinedType:
        """Get the status value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class StellantisActionableEntity(StellantisBaseEntity, Generic[T]):
    """Common base for Stellantis entities that can call remote actions."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisVehicleCoordinator,
        description: StellantisEntityDescription,
        entry: StellantisConfigEntry,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, description)
        self.hass = hass
        self.entry = entry

    @abstractmethod
    def _handle_update_from_successful_remote_action(self, state: T) -> None:
        """Handle successful remote action updates."""
        self.async_write_ha_state()

    async def async_call_remote_action(
        self, remote: Remote, state_if_success: T
    ) -> None:
        """Call a remote action and handle the response."""
        assert self.vehicle.id
        try:
            response_data = await self.coordinator.client.send_remote_to_vhl(
                self.vehicle.id,
                self.entry.data[CONF_CALLBACK_ID],
                remote,
            )
        except StellantisError as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="executing_remote_request_failed",
                translation_placeholders={"failure_cause": str(e) or "Not specified"},
            ) from e

        if not response_data.remote_action_id:
            LOGGER.warning(
                f"The remote action for {self.unique_id} will not be tracked as the remote action ID is missing from the API response"
            )
            return

        try:
            async with timeout(10):
                while True:
                    with StellantisCallbackEvent(
                        self.hass, response_data.remote_action_id
                    ) as callback_event:
                        event_status = await callback_event
                        assert event_status.type == RemoteEventType.DONE
                        match event_status.status:
                            case RemoteDoneEventStatus.FAILED:
                                raise HomeAssistantError(
                                    translation_domain=DOMAIN,
                                    translation_key="remote_request_failed",
                                    translation_placeholders={
                                        "failure_cause": event_status.failure_cause
                                        or "Not specified"
                                    },
                                )
                        self._handle_update_from_successful_remote_action(
                            state_if_success
                        )
                        break
        except TimeoutError:
            LOGGER.warning(
                f"Confirmation of the remote action to {self.unique_id} was not received in time"
            )


@dataclass(frozen=True, kw_only=True)
class StellantisToggleEntityDescription(
    StellantisEntityDescription, ToggleEntityDescription
):
    """Common base description for Stellantis entities that can be toggled."""

    remote_request_on: Remote
    remote_request_off: Remote
    value_fn: Callable[[Status], bool | None]


class StellantisToggleEntity(StellantisActionableEntity[bool], ToggleEntity):
    """Common base class for Stellantis entities that can be toggled."""

    entity_description: StellantisToggleEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send a remote action to turn on something."""
        await self.async_call_remote_action(
            self.entity_description.remote_request_on, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send a remote action to turn off something."""
        await self.async_call_remote_action(
            self.entity_description.remote_request_off, False
        )

    def _handle_update_from_successful_remote_action(self, state: bool) -> None:
        """Handle successful remote action updates."""
        self._attr_is_on = state
        super()._handle_update_from_successful_remote_action(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updates from the coordinator."""
        self._attr_is_on = cast(bool | None, self.status_value)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return true if the vehicle is stopped (or cannot be determined).

        Actionable entities can still be used although the coordinator's last update wasn't successful
        """
        return (
            ignition := self.vehicle_status.ignition
        ) is None or ignition.type == IgnitionType.STOP


class StellantisPreconditioningEntity(StellantisActionableEntity[T], Generic[T]):
    """Common base class for Stellantis preconditioning related entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisVehicleCoordinator,
        description: StellantisEntityDescription,
        entry: StellantisConfigEntry,
        slot: int,
    ) -> None:
        """Initialize entity."""
        super().__init__(hass, coordinator, description, entry)
        self.slot = slot
        self._attr_translation_placeholders = {"slot": str(slot)}

    @property
    def program(self) -> PreconditioningProgram | None:
        """Return the status value of the preconditioning program."""
        if not self.coordinator.last_update_success:
            self._attr_available = True
            return None
        if (
            (preconditioning := self.vehicle_status.preconditioning)
            and (air_conditioning := preconditioning.air_conditioning)
            and (programs := air_conditioning.programs)
        ):
            for program in programs:
                if program.slot == self.slot:
                    self._attr_available = True
                    return program
        self._attr_available = False
        return None

    @property
    def available(self) -> bool:
        """Return available if the program exists."""
        return self._attr_available
