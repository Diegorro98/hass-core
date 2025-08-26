"""Stellantis switch platform."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from stellantis.model import (
    DoorLockedState,
    Remote,
    RemoteDoorsState,
    RemoteDoorsStateEnum,
)

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StellantisConfigEntry
from .entity import StellantisActionableEntity, StellantisToggleEntityDescription


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
    value_fn=lambda status: (
        True
        if DoorLockedState.LOCKED in locked_states
        or DoorLockedState.SUPER_LOCKED in locked_states
        else False
        if DoorLockedState.UNLOCKED in locked_states
        else None
    )
    if (doors_state := status.doors_state)
    and (locked_states := doors_state.locked_states)
    else None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis locks."""
    async_add_entities(
        StellantisDoorsLock(
            hass, vehicle_coordinator, DOORS_LOCK_ENTITY_DESCRIPTION, entry
        )
        for vehicle_coordinator in entry.runtime_data
    )


class StellantisDoorsLock(StellantisActionableEntity[bool], LockEntity):
    """Representation of Stellantis doors lock state."""

    entity_description: StellantisLockEntityDescription

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
        self._attr_is_locked = cast(bool | None, self.status_value)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {
            "locked_states": self.vehicle_status.doors_state.locked_states
            if self.vehicle_status.doors_state
            else None
        }
