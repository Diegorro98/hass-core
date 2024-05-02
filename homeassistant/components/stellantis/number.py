"""Stellantis number platform."""

from typing import Any

from jsonpath import jsonpath

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .const import DOMAIN, LOGGER
from .coordinator import StellantisUpdateCoordinator, VehicleData
from .entity import StellantisBaseActionableEntity


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
                    StellantisChargingPowerLevelNumber(
                        hass,
                        data.coordinator,
                        vehicle_data,
                        entry,
                    ),
                )
            )


class StellantisChargingPowerLevelNumber(StellantisBaseActionableEntity, NumberEntity):
    """Representation of Stellantis charging power level number."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: VehicleData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the charging power level number entity."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            NumberEntityDescription(
                key="charging_power_level",
                translation_key="charging_power_level",
                native_min_value=1,
                native_max_value=5,
                native_step=1,
            ),
            entry,
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self._attr_native_value is not None:
            ret = self._attr_native_value
            self._attr_native_value = None
            return ret

        str_value = self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.chargingPowerLevel"
        )
        try:
            return float(str_value.replace("Level", "")) if str_value else None
        except ValueError:
            LOGGER.debug("Error obtaining charging level from value: %s", str_value)
            return None

    @property
    def available(self) -> bool:
        """Return available if the program exists."""
        return (self.native_value is not None) and super().available

    async def async_set_native_value(self, value: float) -> None:
        """Set the charging power level."""
        await self.async_call_remote_action(
            {"charging": {"preferences": {"level": f"Level{int(value)}"}}},
            value,
            "set the charging power level",
        )

    def on_remote_action_success(self, state_if_success: Any) -> None:
        """Handle the success of a remote action."""
        self._attr_native_value = state_if_success
