"""Stellantis time platform."""

import copy
from dataclasses import dataclass
from datetime import datetime, time

from stellantis.model import EnergyType, Remote, RemoteCharging, Schedule

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SVE_TRANSLATION_PLACEHOLDER_SLOT
from .coordinator import StellantisConfigEntry
from .entity import (
    StellantisActionableEntity,
    StellantisEntityDescription,
    StellantisPreconditioningEntity,
)
from .helpers import preconditioning_program_setter_body


@dataclass(frozen=True, kw_only=True)
class StellantisTimeEntityDescription(
    StellantisEntityDescription, TimeEntityDescription
):
    """Describes a Stellantis time entity."""


CHARGING_TIME_ENTITY_DESCRIPTION = StellantisTimeEntityDescription(
    key="charging_time",
    translation_key="charging_time",
    value_fn=lambda status: charging.next_delayed_time
    if (
        energy := next(
            (
                energy
                for energy in status.energies or []
                if energy.type == EnergyType.ELECTRIC
            ),
            None,
        )
    )
    and (extension := energy.extension)
    and (electric := extension.electric)
    and (charging := electric.charging)
    else None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""
    entities: list[TimeEntity] = []
    for vehicle_coordinator in entry.runtime_data:
        if (
            vehicle_coordinator.data.preconditioning
            and vehicle_coordinator.data.preconditioning.air_conditioning
        ):
            entities.extend(
                StellantisPreconditioningProgramStartTime(
                    hass,
                    vehicle_coordinator,
                    StellantisEntityDescription(
                        key=f"preconditioning_program_{slot}_start_time",
                        translation_key=f"preconditioning_program_{slot}_start_time",
                        value_fn=lambda _: None,
                    ),
                    entry,
                    slot,
                )
                for slot in range(1, 5)
            )

        if next(
            (
                energy
                for energy in vehicle_coordinator.data.energies or []
                if energy.type == EnergyType.ELECTRIC
            ),
            None,
        ):
            entities.append(
                StellantisChargingTime(
                    hass,
                    vehicle_coordinator,
                    CHARGING_TIME_ENTITY_DESCRIPTION,
                    entry,
                )
            )
    async_add_entities(entities)


class StellantisPreconditioningProgramStartTime(
    StellantisPreconditioningEntity[time], TimeEntity
):
    """Representation of a Stellantis preconditioning start time of a program."""

    entity_description: StellantisTimeEntityDescription

    def _handle_update_from_successful_remote_action(self, state: time) -> None:
        """Handle successful remote action updates."""
        if self.program != UNDEFINED:
            self._attr_native_value = state
            super()._handle_update_from_successful_remote_action(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = (
            (datetime(1, 1, 1) + start_time).time()
            if self.program != UNDEFINED
            and (start_time := dt_util.parse_duration(self.program.start))
            else None
        )

    async def async_set_value(self, value: time) -> None:
        """Set the start of the preconditioning program."""
        if self.program == UNDEFINED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="preconditioning_program_not_defined",
                translation_placeholders={
                    SVE_TRANSLATION_PLACEHOLDER_SLOT: str(self.slot)
                },
            )

        program = copy.deepcopy(self.program)
        program.start = f"PT{value.hour}H{value.minute}M"
        await self.async_call_remote_action(
            preconditioning_program_setter_body(program), value
        )


class StellantisChargingTime(StellantisActionableEntity[time], TimeEntity):
    """Representation of a Stellantis charging time."""

    entity_description: StellantisTimeEntityDescription

    @callback
    def _handle_update_from_successful_remote_action(self, state: time) -> None:
        """Handle successful remote action updates."""
        self._attr_native_value = state
        super()._handle_update_from_successful_remote_action(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = (
            (datetime(1, 1, 1) + value).time()
            if isinstance(self.status_value, str)
            and (value := dt_util.parse_duration(self.status_value))
            else None
        )

    async def async_set_value(self, value: time) -> None:
        """Set the start of the charging program."""
        await self.async_call_remote_action(
            Remote(
                charging=RemoteCharging(
                    schedule=Schedule(
                        next_delayed_time=f"PT{value.hour}H{value.minute}M"
                    )
                )
            ),
            value,
        )
