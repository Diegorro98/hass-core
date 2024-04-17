"""Stellantis sensor platform."""

from dataclasses import dataclass

from jsonpath import jsonpath
from stringcase import snakecase

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .const import DOMAIN
from .entity import StellantisBaseEntity


@dataclass(frozen=True, kw_only=True)
class StellantisBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Stellantis sensor entity."""

    value_path: str
    true_value: str | None = None


ELECTRIC_ENERGY_BINARY_SENSORS: tuple[StellantisBinarySensorEntityDescription, ...] = (
    StellantisBinarySensorEntityDescription(
        key="plugged",
        translation_key="plugged",
        device_class=BinarySensorDeviceClass.PLUG,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.charging.plugged",
    ),
)


BINARY_SENSORS: tuple[StellantisBinarySensorEntityDescription, ...] = (
    StellantisBinarySensorEntityDescription(
        key="driver_belt_status",
        translation_key="driver_belt_status",
        value_path="$.safety.beltStatus[?(@.id == 'Driver')].belt",
        true_value="Normal",
    ),
    StellantisBinarySensorEntityDescription(
        key="passenger_belt_status",
        translation_key="passenger_belt_status",
        value_path="$.safety.beltStatus[?(@.id == 'Passenger')].belt",
        true_value="Normal",
    ),
    StellantisBinarySensorEntityDescription(
        key="moving",
        translation_key="moving",
        device_class=BinarySensorDeviceClass.MOVING,
        value_path="$.kinetic.moving",
    ),
    StellantisBinarySensorEntityDescription(
        key="environment_light",
        translation_key="environment_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_path="$.environment.luminosity.day",
    ),
    StellantisBinarySensorEntityDescription(
        key="front_turn_right_light",
        translation_key="front_turn_right_light",
        value_path="$.lightingSystem.turn[?(@.direction == 'Right' && @.position == 'Front')].status",
        true_value="On",
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_turn_right_light",
        translation_key="rear_turn_right_light",
        value_path="$.lightingSystem.turn[?(@.direction == 'Right' && @.position == 'Rear')].status",
        true_value="On",
    ),
    StellantisBinarySensorEntityDescription(
        key="front_turn_left_light",
        translation_key="front_turn_left_light",
        value_path="$.lightingSystem.turn[?(@.direction == 'Left' && @.position == 'Front')].status",
        true_value="On",
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_turn_left_light",
        translation_key="rear_turn_left_light",
        value_path="$.lightingSystem.turn[?(@.direction == 'Left' && @.position == 'Rear')].status",
        true_value="On",
    ),
    StellantisBinarySensorEntityDescription(
        key="front_right_fog_light",
        translation_key="front_right_fog_light",
        value_path="$.lightingSystem.fog[?(@.direction == 'Right' && @.position == 'Front')].status",
        true_value="On",
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_right_fog_light",
        translation_key="rear_right_fog_light",
        value_path="$.lightingSystem.fog[?(@.direction == 'Right' && @.position == 'Rear')].status",
        true_value="On",
    ),
    StellantisBinarySensorEntityDescription(
        key="front_left_fog_light",
        translation_key="front_left_fog_light",
        value_path="$.lightingSystem.fog[?(@.direction == 'Left' && @.position == 'Front')].status",
        true_value="On",
    ),
    StellantisBinarySensorEntityDescription(
        key="rear_left_fog_light",
        translation_key="rear_left_fog_light",
        value_path="$.lightingSystem.fog[?(@.direction == 'Left' && @.position == 'Rear')].status",
        true_value="On",
    ),
)


def get_door_states_sensors(
    door_states: list[dict[str, str]],
) -> tuple[StellantisBinarySensorEntityDescription, ...]:
    """Get door states binary sensors."""
    return tuple(
        [
            StellantisBinarySensorEntityDescription(
                key=f"{snakecase(door_state['id'])}{'_door' if door_state['identifier'].endswith("Window") else ''}_state",
                translation_key=f"{snakecase(door_state['id'])}{'_door' if door_state['identifier'].endswith("Window") else ''}_state",
                device_class=BinarySensorDeviceClass.DOOR,
                value_path=f"$doorState.opening[[?(@.identifier == {door_state}]",
                true_value="Open",
            )
            for door_state in door_states
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis sensors."""

    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    for vehicle_data in data.coordinator.vehicles_data:
        sensors = BINARY_SENSORS

        if jsonpath(
            data.coordinator.vehicles_status,
            f"$.{vehicle_data.vin}.energies[?(@.type == 'Electric')]",
        ):
            sensors += ELECTRIC_ENERGY_BINARY_SENSORS

        if matches := jsonpath(
            data.coordinator.vehicles_status, f"${vehicle_data.vin}.doorState.opening"
        ):
            sensors += get_door_states_sensors(matches)

        async_add_entities(
            StellantisBinarySensor(
                data.coordinator,
                vehicle_data,
                description,
            )
            for description in sensors
        )


class StellantisBinarySensor(StellantisBaseEntity, BinarySensorEntity):
    """Representation of a Stellantis sensor."""

    entity_description: StellantisBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Calculate the sensor value from the entity description."""
        value = self.get_from_vehicle_status(self.entity_description.value_path)
        if isinstance(value, str):
            return value == self.entity_description.true_value
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.is_on is not None and super().available
