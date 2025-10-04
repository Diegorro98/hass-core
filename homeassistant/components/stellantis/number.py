"""Stellantis number platform."""

from dataclasses import dataclass

from stellantis.model import (
    ChargingPowerLevel,
    Remote,
    RemoteCharging,
    RemoteChargingPreferences,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StellantisConfigEntry
from .entity import StellantisActionableEntity, StellantisEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class StellantisNumberEntityDescription(
    StellantisEntityDescription, NumberEntityDescription
):
    """Describes a Stellantis number entity."""


POWER_LEVEL_ENTITY_DESCRIPTION = StellantisNumberEntityDescription(
    key="charging_power_level",
    translation_key="charging_power_level",
    value_fn=lambda _: None,
    native_min_value=1,
    native_max_value=5,
    native_step=1,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""
    async_add_entities(
        StellantisChargingPowerLevelNumber(
            vehicle_coordinator,
            POWER_LEVEL_ENTITY_DESCRIPTION,
            remote is None or level is None,
        )
        for vehicle_coordinator in entry.runtime_data.vehicle_coordinators
        if (
            remote := (
                embedded.extension.onboard_capabilities.remote
                if (embedded := vehicle_coordinator.vehicle.embedded)
                and embedded.extension
                and embedded.extension.onboard_capabilities
                else None
            )
        )
        is None
        or (
            remote.charging.supported is True
            and (
                level := (
                    remote.charging.parameters.preferences.level
                    if remote.charging.parameters
                    and remote.charging.parameters.preferences
                    else None
                )
            )
            is not False
        )
    )


class StellantisChargingPowerLevelNumber(
    StellantisActionableEntity[float], NumberEntity
):
    """Representation of Stellantis charging power level number."""

    entity_description: StellantisNumberEntityDescription

    def _handle_update_from_successful_remote_action(self, state: float) -> None:
        """Handle successful remote action updates."""
        self._attr_native_value = state
        super()._handle_update_from_successful_remote_action(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = None
        if (
            (
                energy := next(
                    (
                        energy
                        for energy in (self.vehicle_status.energies or [])
                        if energy.type == "Electric"
                    ),
                    None,
                )
            )
            and (extension := energy.extension)
            and (electric := extension.electric)
            and (charging := electric.charging)
            and (charging_power_level := charging.charging_power_level)
        ):
            self._attr_native_value = float(
                charging_power_level.value.removeprefix("Level")
            )
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set the charging power level."""
        await self.async_call_remote_action(
            Remote(
                charging=RemoteCharging(
                    preferences=RemoteChargingPreferences(
                        level=ChargingPowerLevel(f"Level{int(value)}")
                    )
                )
            ),
            value,
        )
