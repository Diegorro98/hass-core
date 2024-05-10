"""Stellantis switch platform."""

from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .api import StellantisVehicle
from .const import DOMAIN
from .coordinator import StellantisUpdateCoordinator
from .entity import StellantisBaseActionableEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis locks."""

    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    # In the future, when "onboardCapabilities" extension header works, we will know
    # whether to add the door lock if the vehicle has the capability to lock/unlock the doors remotely.
    async_add_entities(
        StellantisDoorsLock(
            hass,
            data.coordinator,
            vehicle_data,
            entry,
        )
        for vehicle_data in data.coordinator.data
    )


class StellantisDoorsLock(StellantisBaseActionableEntity[bool], LockEntity):
    """Representation of Stellantis doors lock state."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the doors lock."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            LockEntityDescription(
                key="doors",
                translation_key="doors",
            ),
            entry,
        )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the doors."""
        await self.async_call_remote_action(
            {"door": {"state": "Locked"}},
            True,
            "lock the vehicle",
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the doors."""
        await self.async_call_remote_action(
            {"door": {"state": "Unlocked"}},
            True,
            "lock the vehicle",
        )

    @property
    def status_value(self):
        """Return the state reported from the API."""
        return self.get_from_vehicle_status("$.doorsState.lockedStates")

    @property
    def is_locked(self) -> bool | None:
        """Return the lock state of the doors."""
        if self._attr_remote_action_value is not None:
            ret = self._attr_remote_action_value
            self._attr_remote_action_value = None
            return ret

        try:
            locked_states = self.status_value
            if locked_states:
                if ("Locked", "SuperLocked") in locked_states:
                    return True
                if "Unlocked" in locked_states:
                    return False
        except KeyError:
            pass
        return None

    @property
    def available(self) -> bool:
        """Return true if the vehicle is turned off."""
        try:
            _ = self.status_value
        except KeyError:
            return False
        return super().available
