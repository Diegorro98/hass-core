"""Stellantis switch platform."""

from asyncio import timeout
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .api import StellantisVehicle
from .const import (
    ATTR_EVENT_TYPE,
    ATTR_FAILURE_CAUSE,
    ATTR_REMOTE_ACTION_ID,
    ATTR_STATUS,
    CONF_CALLBACK_ID,
    DOMAIN,
    LOGGER,
)
from .coordinator import StellantisUpdateCoordinator
from .entity import StellantisBaseEntity
from .webhook import StellantisCallbackEvent


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


class StellantisDoorsLock(StellantisBaseEntity, LockEntity):
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
            coordinator,
            vehicle,
            LockEntityDescription(
                key="doors",
                translation_key="doors",
            ),
        )
        self.hass = hass
        self.entry = entry

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the doors."""
        async with timeout(10):
            response_data = await self.coordinator.api.async_send_remote_action(
                self.vehicle.details.id,
                self.entry.data[CONF_CALLBACK_ID],
                {"door": {"state": "Locked"}},
            )

        if ATTR_REMOTE_ACTION_ID not in response_data:
            LOGGER.warning(
                "The remote action to lock the vehicle will not be followed because the remote action ID is missing from the API response"
            )

        with StellantisCallbackEvent(
            self.hass, response_data[ATTR_REMOTE_ACTION_ID]
        ) as callback_event:
            try:
                async with timeout(10):
                    event_status = await callback_event
                    if (
                        event_status[ATTR_EVENT_TYPE] == "Done"
                        and event_status[ATTR_STATUS] == "Failed"
                    ):
                        raise HomeAssistantError(
                            f"Remote action failed. Cause: {event_status[ATTR_FAILURE_CAUSE]}"
                        )
                    self._attr_is_locked = True
            except TimeoutError:
                LOGGER.warning(
                    "Confirmation of the remote action to lock he remote action to set the vehicle to charge immediately was not received in time"
                )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the doors."""
        async with timeout(10):
            response_data = await self.coordinator.api.async_send_remote_action(
                self.vehicle.details.id,
                self.entry.data[CONF_CALLBACK_ID],
                {"door": {"state": "Unlocked"}},
            )

        if ATTR_REMOTE_ACTION_ID not in response_data:
            LOGGER.warning(
                "The remote action to unlock the vehicle will not be followed because the remote action ID is missing from the API response"
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
                    self._attr_is_locked = False
            except TimeoutError:
                LOGGER.warning(
                    "Confirmation of the remote action to unlock the vehicle was not received in time"
                )

    @property
    def is_locked(self) -> bool | None:
        """Return the lock state of the doors."""
        if self._attr_is_locked is not None:
            ret = self._attr_is_locked
            self._attr_is_locked = None
            return ret
        locked_states = self.get_from_vehicle_status("$.doorsState.lockedStates")
        if locked_states:
            if ("Locked", "SuperLocked") in locked_states:
                return True
            if "Unlocked" in locked_states:
                return False
        return None

    @property
    def available(self) -> bool:
        """Return true if the vehicle is turned off."""
        return (
            self.get_from_vehicle_status("$.ignition.type") == "Stop"
            and super().available
        )
