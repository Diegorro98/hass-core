"""Stellantis switch platform."""

from dataclasses import dataclass
from functools import partial
from typing import Any

from stellantis.model import (
    DoorLockedState,
    IgnitionType,
    Remote,
    RemoteDoorsState,
    RemoteDoorsStateEnum,
)

from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
    LockEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StellantisConfigEntry
from .entity import StellantisActionableEntity, StellantisToggleEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class StellantisLockEntityDescription(
    StellantisToggleEntityDescription, LockEntityDescription
):
    """Describes Stellantis lock entity."""


DOORS_LOCK_ENTITY_DESCRIPTION = StellantisLockEntityDescription(
    key="doors",
    translation_key="doors",
    remote_request_on=Remote(door=RemoteDoorsState(state=RemoteDoorsStateEnum.LOCKED)),
    remote_request_off=Remote(
        door=RemoteDoorsState(state=RemoteDoorsStateEnum.UNLOCKED)
    ),
    value_fn=lambda _: None,
)


def _check_vehicles_and_add_entities(
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    known_vehicles: set[str],
) -> None:
    coordinator_data = entry.runtime_data.coordinator.data
    current_vehicles = set(coordinator_data.keys())
    new_vehicles = current_vehicles - known_vehicles
    no_longer_known_vehicles = known_vehicles - current_vehicles
    for vin in no_longer_known_vehicles:
        known_vehicles.remove(vin)
    known_vehicles.update(new_vehicles)

    entities: list[StellantisDoorsLock] = []
    for vehicle_vin in new_vehicles:
        vehicle_coordinator = coordinator_data[vehicle_vin]

        if (
            lock_supported := (
                embedded.extension.onboard_capabilities.remote.door.supported
                if (embedded := vehicle_coordinator.vehicle.embedded)
                and embedded.extension
                and embedded.extension.onboard_capabilities
                and embedded.extension.onboard_capabilities.remote
                else None
            )
        ) is not False:
            entities.append(
                StellantisDoorsLock(
                    vehicle_coordinator,
                    DOORS_LOCK_ENTITY_DESCRIPTION,
                    lock_supported is None,
                )
            )

    if entities:
        async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""
    known_vehicles: set[str] = set()

    entry.async_on_unload(
        entry.runtime_data.coordinator.async_add_listener(
            partial(
                _check_vehicles_and_add_entities,
                entry,
                async_add_entities,
                known_vehicles,
            )
        )
    )


class StellantisDoorsLock(StellantisActionableEntity[bool], LockEntity):
    """Representation of Stellantis doors lock state."""

    entity_description: StellantisLockEntityDescription
    _attr_supported_features: LockEntityFeature = LockEntityFeature.OPEN

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the doors."""
        await self.async_call_remote_action(
            self.entity_description.remote_request_on, True
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the doors."""
        await self.async_call_remote_action(
            self.entity_description.remote_request_off, False
        )

    def _handle_update_from_successful_remote_action(self, state: bool) -> None:
        """Handle successful remote action updates."""
        self._attr_is_locked = state
        super()._handle_update_from_successful_remote_action(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_locked = None
        self._attr_extra_state_attributes = {}
        if (doors_state := self.vehicle_status.doors_state) and (
            locked_states := doors_state.locked_states
        ):
            self._attr_is_locked = (
                True
                if DoorLockedState.LOCKED in locked_states
                or DoorLockedState.SUPER_LOCKED in locked_states
                else False
                if DoorLockedState.UNLOCKED in locked_states
                else None
            )
            self._attr_extra_state_attributes["locked_states"] = locked_states
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return true if the vehicle is stopped (or cannot be determined).

        Actionable entities can still be used although the coordinator's last update wasn't successful
        """
        return (
            ignition := self.vehicle_status.ignition
        ) is None or ignition.type == IgnitionType.STOP
