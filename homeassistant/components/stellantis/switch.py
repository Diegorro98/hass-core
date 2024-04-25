"""Stellantis switch platform."""

from jsonpath import jsonpath

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .const import DOMAIN
from .coordinator import StellantisUpdateCoordinator, VehicleData
from .entity import StellantisBaseToggleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""

    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    for vehicle_data in data.coordinator.vehicles_data:
        if jsonpath(
            data.coordinator.vehicles_status,
            f"$.{vehicle_data.vin}.energies[?(@.type == 'Electric')]",
        ):
            async_add_entities(
                (
                    StellantisDelayedChargeSwitch(
                        hass,
                        data.coordinator,
                        vehicle_data,
                        entry,
                    ),
                    StellantisPreconditioningSwitch(
                        hass,
                        data.coordinator,
                        vehicle_data,
                        entry,
                    ),
                    StellantisChargingTypeSwitch(
                        hass,
                        data.coordinator,
                        vehicle_data,
                        entry,
                    ),
                )
            )


class StellantisDelayedChargeSwitch(StellantisBaseToggleEntity, SwitchEntity):
    """Representation of Stellantis delayed charge switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: VehicleData,
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
        status = self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.status"
        )
        return None if not status else status == "Stopped"

    @property
    def available(self) -> bool:
        """Return true if the the vehicle has is able to control the charge."""
        charging_status = self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.status"
        )
        return super().available and charging_status in ("stopped", "in_progress")


class StellantisPreconditioningSwitch(StellantisBaseToggleEntity, SwitchEntity):
    """Representation of Stellantis preconditioning switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: VehicleData,
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
        status = self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.status"
        )
        return None if not status else status == "Stopped"

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
        doors_lock_state = self.get_from_vehicle_status("$.doorsState.lockedStates")
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


class StellantisChargingTypeSwitch(StellantisBaseToggleEntity, SwitchEntity):
    """Representation of Stellantis partial charge switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: VehicleData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the partial charge switch."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            SwitchEntityDescription(
                key="charging_type",
                translation_key="charging_type",
            ),
            entry,
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
        status = self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.type"
        )
        return None if not status else status == "Partial"

    @property
    def available(self) -> bool:
        """Return true if the the vehicle has is able to control the charge."""
        charging_status = self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.status"
        )
        return super().available and charging_status in ("stopped", "in_progress")
