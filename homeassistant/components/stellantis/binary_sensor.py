"""Stellantis sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from stellantis.model import (
    BeltStatusEnum,
    DoorIdentifier,
    DoorOpeningStateEnum,
    EnergyType,
    Light,
    LightDirection,
    LightPosition,
    LightStatus,
    Motorization,
    SeatId,
    Status,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .coordinator import StellantisConfigEntry
from .entity import StellantisBaseEntity, StellantisEntityDescription
from .helpers import get_energy


class LightTypes(StrEnum):
    """Light types.

    Possible light types from LightingSystem
    """

    TURN = "turn"
    FOG = "fog"


@dataclass(frozen=True, kw_only=True)
class StellantisBinarySensorEntityDescription(
    StellantisEntityDescription, BinarySensorEntityDescription
):
    """Describes Stellantis sensor entity."""

    value_fn: Callable[[Status], bool | None | UndefinedType]


def _get_belt_value_fn(
    seat_id: SeatId,
) -> Callable[[Status], bool | None | UndefinedType]:
    def _get_belt_value(status: Status) -> bool | None | UndefinedType:
        if status.safety:
            for belt in status.safety.belt_status or []:
                if belt.id == seat_id:
                    return belt.belt == BeltStatusEnum.NORMAL if belt.belt else None
        return UNDEFINED

    return _get_belt_value


def _get_light_value_fn(
    position: LightPosition,
    direction: LightDirection,
    type: LightTypes,
) -> Callable[[Status], bool | UndefinedType | None]:
    def _get_light_value(status: Status) -> bool | None | UndefinedType:
        if status.lighting_system and (
            lights := cast(list[Light] | None, getattr(status.lighting_system, type))
        ):
            for light in lights:
                if light.direction == direction and light.position == position:
                    return light.status == LightStatus.ON if light.status else None
        return UNDEFINED

    return _get_light_value


def _get_door_value_fn(
    identifier: DoorIdentifier,
) -> Callable[[Status], bool | None | UndefinedType]:
    def _get_door_value(
        status: Status,
    ) -> bool | None | UndefinedType:
        """Get the door state."""
        if status.doors_state and (doors := status.doors_state.opening):
            for door in doors:
                if door.identifier == identifier:
                    if door.state is None:
                        return None
                    return door.state == DoorOpeningStateEnum.OPEN
        return UNDEFINED

    return _get_door_value


ELECTRIC_ENERGY_BINARY_SENSORS = (
    StellantisBinarySensorEntityDescription(
        key="plugged",
        translation_key="plugged",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda status: charging.plugged
        if (energy := get_energy(status, EnergyType.ELECTRIC))
        and (extension := energy.extension)
        and (electric := extension.electric)
        and (charging := electric.charging)
        else UNDEFINED,
    ),
)


BINARY_SENSORS = (
    *[
        StellantisBinarySensorEntityDescription(
            key=(key := f"{seat_name.lower()}_belt_status"),
            translation_key=key,
            value_fn=_get_belt_value_fn(seat_id),
        )
        for seat_name, seat_id in SeatId.__members__.items()
    ],
    StellantisBinarySensorEntityDescription(
        key="moving",
        translation_key="moving",
        device_class=BinarySensorDeviceClass.MOVING,
        value_fn=lambda status: status.kinetic.moving if status.kinetic else UNDEFINED,
    ),
    StellantisBinarySensorEntityDescription(
        key="environment_light",
        translation_key="environment_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: luminosity.day
        if (environment := status.environment)
        and (luminosity := environment.luminosity)
        else UNDEFINED,
    ),
    *[
        StellantisBinarySensorEntityDescription(
            key=(
                key
                := f"{position_name.lower()}_{direction_name.lower()}_{_type_name.lower()}_light"
            ),
            translation_key=key,
            device_class=BinarySensorDeviceClass.LIGHT,
            value_fn=_get_light_value_fn(position, direction, _type),
        )
        for _type_name, _type in LightTypes.__members__.items()
        for direction_name, direction in LightDirection.__members__.items()
        for position_name, position in LightPosition.__members__.items()
    ],
    *[
        StellantisBinarySensorEntityDescription(
            device_class=BinarySensorDeviceClass.DOOR
            if (
                is_door := door_identifier
                not in (DoorIdentifier.REAR_WINDOW, DoorIdentifier.ROOF_WINDOW)
            )
            else BinarySensorDeviceClass.WINDOW,
            key=(key := f"{door_identifier_name.lower()}{'_door' if is_door else ''}"),
            translation_key=key,
            value_fn=_get_door_value_fn(door_identifier),
        )
        for door_identifier_name, door_identifier in DoorIdentifier.__members__.items()
    ],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis sensors."""

    entities: list[StellantisBinarySensor] = []
    for vehicle_coordinator in entry.runtime_data:
        sensors: list[StellantisBinarySensorEntityDescription] = []

        if vehicle_coordinator.vehicle.motorization in (
            Motorization.ELECTRIC,
            Motorization.HYBRID,
        ):
            sensors += ELECTRIC_ENERGY_BINARY_SENSORS

        entities.extend(
            StellantisBinarySensor(
                vehicle_coordinator,
                description,
            )
            for description in list(BINARY_SENSORS) + sensors
        )

    async_add_entities(entities)


class StellantisBinarySensor(StellantisBaseEntity, BinarySensorEntity):
    """Representation of a Stellantis sensor."""

    entity_description: StellantisBinarySensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updates from the coordinator."""
        status_value = self.status_value
        self._attr_is_on = (
            cast(bool | None, status_value) if status_value is not UNDEFINED else None
        )
        self._attr_available = status_value is not UNDEFINED
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._attr_available
