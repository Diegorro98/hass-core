"""Stellantis time platform."""

import copy
from dataclasses import dataclass
from datetime import datetime, time
from functools import partial

from stellantis.model import (
    EnergyType,
    Remote,
    RemoteCharging,
    Schedule,
    ScheduleProgram,
)

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import StellantisConfigEntry, StellantisVehicleCoordinator
from .entity import (
    StellantisActionableEntity,
    StellantisChargingProgramEntity,
    StellantisEntityDescription,
    StellantisPreconditioningEntity,
)
from .helpers import preconditioning_program_setter_body, time_to_iso_duration

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class StellantisTimeEntityDescription(
    StellantisEntityDescription, TimeEntityDescription
):
    """Describes a Stellantis time entity."""


PRECONDITIONING_PROGRAM_TIME_ENTITY_DESCRIPTION = StellantisEntityDescription(
    key="preconditioning_program",
    translation_key="preconditioning_program",
    value_fn=lambda _: None,
)

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

CHARGING_PROGRAM_TIME_ENTITY_DESCRIPTIONS = {
    "start": StellantisTimeEntityDescription(
        key="charging_program_start",
        translation_key="charging_program_start",
        value_fn=lambda _: None,
    ),
    "end": StellantisTimeEntityDescription(
        key="charging_program_end",
        translation_key="charging_program_end",
        value_fn=lambda _: None,
    ),
}


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

    entities: list[TimeEntity] = []
    for vehicle_vin in new_vehicles:
        vehicle_coordinator = coordinator_data[vehicle_vin]

        remote = (
            embedded.extension.onboard_capabilities.remote
            if (embedded := vehicle_coordinator.vehicle.embedded)
            and embedded.extension
            and embedded.extension.onboard_capabilities
            else None
        )
        if remote is None or (
            remote.preconditioning.supported is True
            and (
                size := (
                    remote.preconditioning.parameters.programs.size
                    if remote.preconditioning.parameters
                    and remote.preconditioning.parameters.programs
                    else None
                )
            )
            != 0
        ):
            entities.extend(
                StellantisPreconditioningProgramStartTime(
                    vehicle_coordinator,
                    PRECONDITIONING_PROGRAM_TIME_ENTITY_DESCRIPTION,
                    slot,
                    remote is None or size is None,
                )
                for slot in range(
                    1,
                    5 if remote is None or size is None else size + 1,
                )
            )

        if remote is None or (remote.charging.supported is True):
            if (
                remote is None
                or (
                    next_delayed_time_supported := (
                        remote.charging.parameters.schedule.next_delayed_time
                        if remote.charging.parameters.schedule
                        else None
                    )
                )
                is not False
            ):
                entities.append(
                    StellantisChargingTime(
                        vehicle_coordinator,
                        CHARGING_TIME_ENTITY_DESCRIPTION,
                        remote is None or next_delayed_time_supported is None,
                    )
                )
            if (
                remote is None
                or (
                    charging_programs_support := (
                        remote.charging.parameters.schedule.programs
                        if remote.charging.parameters.schedule
                        else None
                    )
                )
                is None
                or (
                    charging_programs_support.supported is True
                    and (num_charging_programs := charging_programs_support.size) != 0
                )
            ):
                entities.extend(
                    StellantisChargingProgramTime(
                        vehicle_coordinator,
                        CHARGING_PROGRAM_TIME_ENTITY_DESCRIPTIONS[attribute],
                        slot,
                        attribute,
                        remote is None
                        or charging_programs_support is None
                        or num_charging_programs is None,
                    )
                    for attribute in ("start", "end")
                    for slot in range(
                        1,
                        5
                        if remote is None
                        or charging_programs_support is None
                        or num_charging_programs is None
                        else num_charging_programs + 1,
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


class StellantisPreconditioningProgramStartTime(
    StellantisPreconditioningEntity[time], TimeEntity
):
    """Representation of a Stellantis preconditioning start time of a program."""

    entity_description: StellantisTimeEntityDescription

    def _handle_update_from_successful_remote_action(self, state: time) -> None:
        """Handle successful remote action updates."""
        if self.program is not None:
            self._attr_native_value = state
            super()._handle_update_from_successful_remote_action(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
        if program := self.program:
            self._attr_native_value = (
                (datetime(1, 1, 1) + start_time).time()
                if (start_time := dt_util.parse_duration(program.start))
                else None
            )
            self._attr_extra_state_attributes.update(
                {
                    "recurrence": program.recurrence,
                    "occurrence": program.occurence,  # codespell:ignore occurence
                }
            )

        super()._handle_coordinator_update()

    async def async_set_value(self, value: time) -> None:
        """Set the start of the preconditioning program."""
        program = copy.deepcopy(self.program)
        # The program must be defined, otherwise the entity is unavailable
        # and this method cannot be called
        assert program is not None

        program.start = time_to_iso_duration(value)
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
            if isinstance((status_value := self.status_value), str)
            and (value := dt_util.parse_duration(status_value))
            else None
        )
        super()._handle_coordinator_update()

    async def async_set_value(self, value: time) -> None:
        """Set the start of the charging program."""
        await self.async_call_remote_action(
            Remote(
                charging=RemoteCharging(
                    schedule=Schedule(next_delayed_time=time_to_iso_duration(value))
                )
            ),
            value,
        )

    @property
    def available(self) -> bool:
        """This entity is always available."""
        return True


class StellantisChargingProgramTime(StellantisChargingProgramEntity[time], TimeEntity):
    """Representation of a Stellantis charging program start/end time entity."""

    entity_description: StellantisTimeEntityDescription

    def __init__(
        self,
        coordinator: StellantisVehicleCoordinator,
        description: StellantisTimeEntityDescription,
        slot: int,
        attribute: str,
        unknown_supported: bool = True,
    ) -> None:
        """Initialize the charging program start/end time entity."""
        super().__init__(coordinator, description, slot, unknown_supported)
        self.attribute = attribute
        assert attribute in ("start", "end")

    def _handle_update_from_successful_remote_action(self, state: time) -> None:
        """Handle successful remote action updates."""
        if self.program is not None:
            self._attr_native_value = state
            super()._handle_update_from_successful_remote_action(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

        if program := self.program:
            self._attr_native_value = (
                (datetime(1, 1, 1) + _time).time()
                if (_time := dt_util.parse_duration(getattr(program, self.attribute)))
                else None
            )
            if occurrence := program.occurence:  # codespell:ignore occurence
                self._attr_extra_state_attributes.update({"occurrence": occurrence.day})

        super()._handle_coordinator_update()

    async def async_set_value(self, value: time) -> None:
        """Set the start of the preconditioning program."""
        programs = [
            ScheduleProgram(
                start=program.start,
                end=program.end,
                enabled=program.enabled,
                occurence=copy.deepcopy(  # codespell:ignore occurence
                    program.occurence  # codespell:ignore occurence
                ),
            )
            for program in self.programs or []
        ]
        assert programs is not None
        assert self.slot - 1 < len(programs)
        # The program must be defined, otherwise the entity is unavailable
        # and this method cannot be called
        program = programs[self.slot - 1]

        setattr(program, self.attribute, time_to_iso_duration(value))
        await self.async_call_remote_action(
            Remote(charging=RemoteCharging(schedule=Schedule(programs=programs))),
            value,
        )
