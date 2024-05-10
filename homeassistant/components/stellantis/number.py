"""Stellantis number platform."""

from jsonpath import jsonpath

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .api import StellantisVehicle
from .const import DOMAIN, LOGGER
from .coordinator import StellantisUpdateCoordinator
from .entity import StellantisBaseActionableEntity


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
            "$.energies[?(@.type == 'Electric')]",
        ):
            async_add_entities(
                (
                    StellantisChargingPowerLevelNumber(
                        hass,
                        data.coordinator,
                        vehicle,
                        entry,
                    ),
                )
            )


class StellantisChargingPowerLevelNumber(
    StellantisBaseActionableEntity[float], NumberEntity
):
    """Representation of Stellantis charging power level number."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: StellantisVehicle,
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
    def status_value(self):
        """Return the state reported from the API."""
        return self.get_from_vehicle_status(
            "$.energies[?(@.type == 'Electric')].extension.electric.charging.chargingPowerLevel"
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self._attr_remote_action_value is not None:
            ret = self._attr_remote_action_value
            self._attr_remote_action_value = None
            return ret

        str_value = self.status_value
        try:
            return float(str_value.replace("Level", "")) if str_value else None
        except ValueError:
            LOGGER.debug("Error obtaining charging level from value: %s", str_value)
            return None

    @property
    def available(self) -> bool:
        """Return available if the program exists."""
        try:
            _ = self.status_value
        except KeyError:
            return False
        return super().available

    async def async_set_native_value(self, value: float) -> None:
        """Set the charging power level."""
        await self.async_call_remote_action(
            {"charging": {"preferences": {"level": f"Level{int(value)}"}}},
            value,
            "set the charging power level",
        )
