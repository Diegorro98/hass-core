"""Stellantis switch platform."""

import copy
from dataclasses import dataclass
from typing import Any

from stellantis.model import (
    AirConditioningStatus,
    ChargingStatusEnum,
    ChargingType,
    DoorLockedState,
    EnergyType,
    Motorization,
    Remote,
    RemoteCharging,
    RemoteChargingPreferences,
    RemotePreconditioning,
    RemotePreconditioningAirConditioning,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED

from .const import DOMAIN, SVE_TRANSLATION_PLACEHOLDER_SLOT
from .coordinator import StellantisConfigEntry
from .entity import (
    StellantisEntityDescription,
    StellantisPreconditioningEntity,
    StellantisToggleEntity,
    StellantisToggleEntityDescription,
)
from .helpers import preconditioning_program_setter_body


@dataclass(frozen=True, kw_only=True)
class StellantisSwitchEntityDescription(
    StellantisToggleEntityDescription, SwitchEntityDescription
):
    """Describes a Stellantis switch entity."""


PRECONDITIONING_SWITCH_ENTITY_DESCRIPTION = StellantisSwitchEntityDescription(
    key="preconditioning",
    translation_key="preconditioning",
    remote_request_on=Remote(
        preconditioning=RemotePreconditioning(
            air_conditioning=RemotePreconditioningAirConditioning(immediate=True)
        )
    ),
    remote_request_off=Remote(
        preconditioning=RemotePreconditioning(
            air_conditioning=RemotePreconditioningAirConditioning(immediate=False)
        )
    ),
    value_fn=lambda status: air_conditioning_status == AirConditioningStatus.ENABLED
    if (preconditioning := status.preconditioning)
    and (air_conditioning := preconditioning.air_conditioning)
    and (air_conditioning_status := air_conditioning.status)
    else None,
)

DELAYED_CHARGE_SWITCH_ENTITY_DESCRIPTION = StellantisSwitchEntityDescription(
    key="partial_charge",
    translation_key="partial_charge",
    remote_request_on=Remote(charging=RemoteCharging(immediate=True)),
    remote_request_off=Remote(charging=RemoteCharging(immediate=False)),
    value_fn=lambda status: charging_status == ChargingStatusEnum.IN_PROGRESS
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
    and (charging_status := charging.status)
    else None,
)

PARTIAL_CHARGE_SWITCH_ENTITY_DESCRIPTION = StellantisSwitchEntityDescription(
    key="partial_charge",
    translation_key="partial_charge",
    remote_request_on=Remote(
        charging=RemoteCharging(
            preferences=RemoteChargingPreferences(type=ChargingType.FULL)
        )
    ),
    remote_request_off=Remote(
        charging=RemoteCharging(
            preferences=RemoteChargingPreferences(type=ChargingType.PARTIAL)
        )
    ),
    value_fn=lambda status: charging_type == ChargingType.PARTIAL
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
    and (charging_type := charging.type)
    else None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""
    entities: list[SwitchEntity] = []
    for vehicle_coordinator in entry.runtime_data:
        if (
            vehicle_coordinator.data.preconditioning
            and vehicle_coordinator.data.preconditioning.air_conditioning
        ):
            entities.extend(
                [
                    StellantisPreconditioningSwitch(
                        hass,
                        vehicle_coordinator,
                        PRECONDITIONING_SWITCH_ENTITY_DESCRIPTION,
                        entry,
                    )
                ]
                + [
                    StellantisPreconditioningProgramSwitch(
                        hass,
                        vehicle_coordinator,
                        StellantisEntityDescription(
                            key=f"preconditioning_program_{slot}",
                            translation_key="preconditioning_program",
                            value_fn=lambda _: None,
                        ),
                        entry,
                        slot,
                    )
                    for slot in range(1, 5)
                ]
            )

        if next(
            (
                energy
                for energy in vehicle_coordinator.data.energies or []
                if energy.type == EnergyType.ELECTRIC
            ),
            None,
        ):
            entities.extend(
                [
                    StellantisChargeRelatedSwitch(
                        hass,
                        vehicle_coordinator,
                        DELAYED_CHARGE_SWITCH_ENTITY_DESCRIPTION,
                        entry,
                    ),
                    StellantisChargeRelatedSwitch(
                        hass,
                        vehicle_coordinator,
                        PARTIAL_CHARGE_SWITCH_ENTITY_DESCRIPTION,
                        entry,
                    ),
                ]
            )

    async_add_entities(entities)


class StellantisPreconditioningSwitch(StellantisToggleEntity, SwitchEntity):
    """Representation of Stellantis preconditioning switch."""

    entity_description: StellantisSwitchEntityDescription

    @property
    def available(self) -> bool:
        """Return true if the the vehicle is able to precondition.

        The conditions are:
        - Car must have a electric engine (this is for all the preconditioning features)
        - Ignition must be off
        - Car must be locked
        - Enough battery
            - For plug-in hybrid cars, the electric battery must be at least 20%
            - For electric cars, the electric battery must be at least 50%
        """
        if not super().available:
            return False

        electric_level = None
        for energies in self.vehicle_status.energies or []:
            if energies.type == EnergyType.ELECTRIC:
                electric_level = energies.level

        if electric_level is None:
            return False

        match self.vehicle.motorization:
            case Motorization.HYBRID:
                if electric_level < 20:
                    return False
            case Motorization.ELECTRIC:
                if electric_level < 50:
                    return False

        if (doors_state := self.vehicle_status.doors_state) and (
            doors_lock_states := doors_state.locked_states
        ):
            if not (
                DoorLockedState.LOCKED in doors_lock_states
                or DoorLockedState.SUPER_LOCKED in doors_lock_states
            ):
                return False
        # If the door lock state does not exist we consider that doors are locked because we can't know the true state

        return True


class StellantisPreconditioningProgramSwitch(
    StellantisPreconditioningEntity[bool], SwitchEntity
):
    """Representation of Stellantis preconditioning program enable switch."""

    entity_description: StellantisSwitchEntityDescription

    async def enable_or_disable_program(self, enabled: bool) -> None:
        """Return the request body to enable or disable a program.

        Because API requires the whole program to be sent, we need to copy the program and set the enabled value.
        """
        if self.program == UNDEFINED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="preconditioning_program_not_defined",
                translation_placeholders={
                    SVE_TRANSLATION_PLACEHOLDER_SLOT: str(self.slot)
                },
            )
        program = copy.deepcopy(self.program)
        program.enabled = enabled
        await self.async_call_remote_action(
            preconditioning_program_setter_body(program), enabled
        )

    def _handle_update_from_successful_remote_action(self, state: bool) -> None:
        """Handle successful remote action updates."""
        if self.program != UNDEFINED:
            self._attr_is_on = state
            super()._handle_update_from_successful_remote_action(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self.program.enabled if self.program != UNDEFINED else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send a remote action to enable preconditioning program."""
        await self.enable_or_disable_program(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send a remote action to disable preconditioning program."""
        await self.enable_or_disable_program(False)


class StellantisChargeRelatedSwitch(StellantisToggleEntity, SwitchEntity):
    """Representation of Stellantis charge control switch."""

    entity_description: StellantisSwitchEntityDescription

    @property
    def charging_status(self) -> ChargingStatusEnum | None:
        """Return the charging status."""
        for energy in self.vehicle_status.energies or []:
            if (
                energy.type == "Electric"
                and (extension := energy.extension)
                and (electric := extension.electric)
                and (charging := electric.charging)
            ):
                return charging.status
        return None

    @property
    def available(self) -> bool:
        """Return true if the charge can be controlled at the moment.

        The car charge can be controlled only if it is in progress or stopped.
        If its unknown, as we don't know the true state, the entity should be available so it can be controlled.
        """
        return super().available and self.charging_status in (
            ChargingStatusEnum.STOPPED,
            ChargingStatusEnum.IN_PROGRESS,
            None,
        )
