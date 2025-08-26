"""Stellantis sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from stellantis.model import (
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .coordinator import StellantisConfigEntry
from .entity import StellantisBaseEntity, StellantisEntityDescription


@dataclass(frozen=True, kw_only=True)
class StellantisBinarySensorEntityDescription(
    StellantisEntityDescription, BinarySensorEntityDescription
):
    """Describes Stellantis sensor entity."""

    value_fn: Callable[[Status], bool | None | UndefinedType]


ELECTRIC_ENERGY_BINARY_SENSORS = (
    StellantisBinarySensorEntityDescription(
        key="plugged",
        translation_key="plugged",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda status: charging.plugged
        if (
            energy := next(
                (
                    energy
                    for energy in (status.energies or [])
                    if energy.type == EnergyType.ELECTRIC
                ),
                None,
            )
        )
        and (extension := energy.extension)
        and (electric := extension.electric)
        and (charging := electric.charging)
        else UNDEFINED,
    ),
)


BINARY_SENSORS = (
    StellantisBinarySensorEntityDescription(
        key="driver_belt_status",
        translation_key="driver_belt_status",
        value_fn=lambda status: belt.belt == "Normal"
        if status.safety
        and (
            belt := next(
                (
                    belt
                    for belt in (status.safety.belt_status or [])
                    if belt.id == SeatId.DRIVER
                ),
                None,
            )
        )
        else UNDEFINED,
    ),
    StellantisBinarySensorEntityDescription(
        key="passenger_belt_status",
        translation_key="passenger_belt_status",
        value_fn=lambda status: belt.belt == "Normal"
        if status.safety
        and (
            belt := next(
                (
                    belt
                    for belt in (status.safety.belt_status or [])
                    if belt.id == SeatId.PASSENGER
                ),
                None,
            )
        )
        else UNDEFINED,
    ),
    StellantisBinarySensorEntityDescription(
        key="moving",
        translation_key="moving",
        device_class=BinarySensorDeviceClass.MOVING,
        value_fn=lambda status: status.kinetic.moving if status.kinetic else None,
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
    StellantisBinarySensorEntityDescription(
        key="front_turn_right_light",
        translation_key="front_turn_right_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: _get_light_value(
            status, LightTypes.TURN, LightPosition.FRONT, LightDirection.RIGHT
        ),
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_turn_right_light",
        translation_key="rear_turn_right_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: _get_light_value(
            status, LightTypes.TURN, LightPosition.REAR, LightDirection.RIGHT
        ),
    ),
    StellantisBinarySensorEntityDescription(
        key="front_turn_left_light",
        translation_key="front_turn_left_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: _get_light_value(
            status, LightTypes.TURN, LightPosition.FRONT, LightDirection.LEFT
        ),
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_turn_left_light",
        translation_key="rear_turn_left_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: _get_light_value(
            status, LightTypes.TURN, LightPosition.REAR, LightDirection.LEFT
        ),
    ),
    StellantisBinarySensorEntityDescription(
        key="front_right_fog_light",
        translation_key="front_right_fog_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: _get_light_value(
            status, LightTypes.FOG, LightPosition.FRONT, LightDirection.RIGHT
        ),
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_right_fog_light",
        translation_key="rear_right_fog_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: _get_light_value(
            status, LightTypes.FOG, LightPosition.REAR, LightDirection.RIGHT
        ),
    ),
    StellantisBinarySensorEntityDescription(
        key="front_left_fog_light",
        translation_key="front_left_fog_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: _get_light_value(
            status, LightTypes.FOG, LightPosition.FRONT, LightDirection.LEFT
        ),
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_left_fog_light",
        translation_key="rear_left_fog_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: _get_light_value(
            status, LightTypes.FOG, LightPosition.REAR, LightDirection.LEFT
        ),
    ),
    StellantisBinarySensorEntityDescription(
        key="driver_door",
        translation_key="driver_door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda status: _get_door_value(status, DoorIdentifier.DRIVER),
    ),
    StellantisBinarySensorEntityDescription(
        key="passenger_door",
        translation_key="passenger_door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda status: _get_door_value(status, DoorIdentifier.PASSENGER),
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_left_door",
        translation_key="rear_left_door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda status: _get_door_value(status, DoorIdentifier.REAR_LEFT),
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_right_door",
        translation_key="rear_right_door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda status: _get_door_value(status, DoorIdentifier.REAR_RIGHT),
    ),
    StellantisBinarySensorEntityDescription(
        key="trunk_door",
        translation_key="trunk_door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda status: _get_door_value(status, DoorIdentifier.TRUNK),
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_window",
        translation_key="rear_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda status: _get_door_value(status, DoorIdentifier.REAR_WINDOW),
    ),
    StellantisBinarySensorEntityDescription(
        key="roof_window",
        translation_key="roof_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda status: _get_door_value(status, DoorIdentifier.ROOF_WINDOW),
    ),
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


class LightTypes(StrEnum):
    """Light types.

    Possible light types from LightingSystem
    """

    TURN = "turn"
    FOG = "fog"


def _get_light_value(
    status: Status,
    type: LightTypes,
    position: LightPosition,
    direction: LightDirection,
) -> bool | None | UndefinedType:
    """Get the light state for a specific direction and position."""
    if status.lighting_system and (
        lights := cast(list[Light] | None, getattr(status.lighting_system, type))
    ):
        for light in lights:
            if light.direction == direction and light.position == position:
                if light.status is None:
                    return None
                return light.status == LightStatus.ON
    return UNDEFINED


def _get_door_value(
    status: Status,
    identifier: DoorIdentifier,
) -> bool | None | UndefinedType:
    """Get the door state."""
    if status.doors_state and (doors := status.doors_state.opening):
        for door in doors:
            if door.identifier == identifier:
                if door.state is None:
                    return None
                return door.state == DoorOpeningStateEnum.OPEN
    return UNDEFINED


class StellantisBinarySensor(StellantisBaseEntity, BinarySensorEntity):
    """Representation of a Stellantis sensor."""

    entity_description: StellantisBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Calculate the sensor value from the entity description."""
        return (
            cast(bool | None, self.status_value)
            if self.status_value is not UNDEFINED
            else None
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.status_value is not UNDEFINED
