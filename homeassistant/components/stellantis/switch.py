"""Stellantis switch platform."""

from typing import Any

from jsonpath import jsonpath

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .api import StellantisVehicle
from .const import ATTR_ENABLED, DOMAIN
from .coordinator import StellantisUpdateCoordinator
from .entity import StellantisBaseToggleEntity
from .helpers import preconditioning_program_setter_body


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""

    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    for vehicle in data.coordinator.data:
        if jsonpath(
            vehicle.status,
            "$.preconditioning.airConditioning",
        ):
            async_add_entities(
                [
                    StellantisPreconditioningSwitch(
                        hass,
                        data.coordinator,
                        vehicle,
                        entry,
                    ),
                ]
                + [
                    StellantisPreconditioningProgramSwitch(
                        hass,
                        data.coordinator,
                        vehicle,
                        entry,
                        slot,
                    )
                    for slot in range(1, 5)
                ]
            )

        if jsonpath(
            vehicle.status,
            "$.energies[?(@.type == 'Electric')]",
        ):
            async_add_entities(
                (
                    StellantisDelayedChargeSwitch(
                        hass,
                        data.coordinator,
                        vehicle,
                        entry,
                    ),
                    StellantisPartialChargeSwitch(
                        hass,
                        data.coordinator,
                        vehicle,
                        entry,
                    ),
                )
            )


class StellantisPreconditioningSwitch(StellantisBaseToggleEntity, SwitchEntity):
    """Representation of Stellantis preconditioning switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the preconditioning switch."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            SwitchEntityDescription(
                key="preconditioning",
                translation_key="preconditioning",
            ),
            entry,
            "$.preconditioning.airConditioning.status",
            {"preconditioning": {"airConditioning": {"immediate": True}}},
            {"preconditioning": {"airConditioning": {"immediate": False}}},
            "turn on preconditioning",
            "turn off preconditioning",
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the charge."""
        if self._attr_is_on is not None:
            ret = self._attr_is_on
            self._attr_is_on = None
            return ret
        return None if not self.status_value else self.status_value == "Enabled"

    @property
    def available(self) -> bool:
        """Return true if the the vehicle is able to precondition.

        The conditions are:
        - Car must have a electric engine
        - Ignition must be off
        - Car must be locked
        - Enough battery
            - For plug-in hybrid cars, the electric battery must be at least 20%
            - For electric cars, the electric battery must be at least 50%
        """
        electric_level = self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].level"
        )
        if not electric_level:
            return False
        try:
            doors_lock_state = self.get_from_vehicle_status("$.doorsState.lockedStates")
        except KeyError:
            doors_lock_state = None
        # If the door lock state does not exist we consider that doors are locked because we can't know the true state
        doors_locked = not doors_lock_state or doors_lock_state not in (
            "Locked",
            "SuperLocked",
        )
        hybrid = len(self.get_from_vehicle_status("$.energies")) == 2
        return (
            super().available
            and doors_locked
            and (
                (hybrid and electric_level > 20) or (not hybrid and electric_level > 50)
            )
        )


class StellantisPreconditioningProgramSwitch(StellantisBaseToggleEntity, SwitchEntity):
    """Representation of Stellantis preconditioning program enable switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        entry: ConfigEntry,
        slot: int,
    ) -> None:
        """Initialize the preconditioning program enable switch."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            SwitchEntityDescription(
                key=f"preconditioning_program_{slot}",
                translation_key=f"preconditioning_program_{slot}",
            ),
            entry,
            f"$.preconditioning.airConditioning.programs[?(@.slot == {slot})]",
            {},
            {},
            f"enable preconditioning program {slot}",
            f"disable preconditioning program {slot}",
        )
        self.slot = slot

    def get_enable_or_disabled_program_request_body(
        self, enabled: bool
    ) -> dict[str, Any]:
        """Return the request body to enable or disable a program.

        Because API requires the whole program to be sent, we need to copy the program and set the enabled value.
        """
        if not self.status_value:
            raise HomeAssistantError(
                f"Preconditioning program {self.slot} does not exists, define it first using stellantis.set_preconditioning_program service"
            )
        self.status_value[ATTR_ENABLED] = enabled
        return preconditioning_program_setter_body(self.status_value)

    @property
    def is_on(self) -> bool | None:
        """Return if the preconditioning program is enabled."""
        return None if not self.status_value else self.status_value["enabled"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send a remote action to enable preconditioning program."""
        request_body = self.get_enable_or_disabled_program_request_body(True)
        await self.async_call_remote_action(request_body, True, self.logger_action_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send a remote action to disable preconditioning program."""
        request_body = self.get_enable_or_disabled_program_request_body(False)
        await self.async_call_remote_action(request_body, False, self.logger_action_off)

    @property
    def available(self) -> bool:
        """Return available if the program exists."""
        try:
            _ = self.status_value
        except KeyError:
            return False
        return self.coordinator.last_update_success


class StellantisDelayedChargeSwitch(StellantisBaseToggleEntity, SwitchEntity):
    """Representation of Stellantis delayed charge switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the delayed charge switch."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            SwitchEntityDescription(
                key="delayed_charge",
                translation_key="delayed_charge",
            ),
            entry,
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.status",
            {"charging": {"immediate": True}},
            {"charging": {"immediate": False}},
            "stop and delay charge",
            "set the vehicle to charge immediately",
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the charge."""
        if self._attr_is_on is not None:
            ret = self._attr_is_on
            self._attr_is_on = None
            return ret
        return None if not self.status_value else self.status_value == "Stopped"

    @property
    def available(self) -> bool:
        """Return true if the the vehicle has is able to control the charge."""
        return super().available and self.status_value in ("Stopped", "InProgress")


class StellantisPartialChargeSwitch(StellantisBaseToggleEntity, SwitchEntity):
    """Representation of Stellantis partial charge switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the partial charge switch."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            SwitchEntityDescription(
                key="partial_charge",
                translation_key="partial_charge",
            ),
            entry,
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.type",
            {"charging": {"preferences": {"type": "Partial"}}},
            {"charging": {"preferences": {"type": "Full"}}},
            "set partial charge",
            "set full charge",
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the charge."""
        if self._attr_is_on is not None:
            ret = self._attr_is_on
            self._attr_is_on = None
            return ret
        return None if not self.status_value else self.status_value == "Partial"

    @property
    def available(self) -> bool:
        """Return true if the the vehicle has is able to control the charge."""
        return super().available and self.status_value in ("Stopped", "InProgress")
