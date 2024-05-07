"""Stellantis sensor platform."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from jsonpath import jsonpath
from stringcase import snakecase

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    WEEKDAYS,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import HomeAssistantStellantisData
from .const import DOMAIN
from .entity import StellantisBaseEntity


@dataclass(frozen=True, kw_only=True)
class StellantisSensorEntityDescription(SensorEntityDescription):
    """Describes Stellantis sensor entity."""

    value_path: str


@dataclass(frozen=True, kw_only=True)
class StellantisPreconditioningSensorEntityDescription(SensorEntityDescription):
    """Describes Stellantis sensor entity."""

    slot: int


FUEL_ENERGY_EXTENSION_SENSORS: tuple[StellantisSensorEntityDescription, ...] = (
    StellantisSensorEntityDescription(
        key="fuel_consumption",
        translation_key="fuel_consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=4,
        value_path="$.energies.[?(@.type == 'Fuel')].extension.fuel.consumptions.total",
    ),
)


ELECTRIC_ENERGY_EXTENSION_SENSORS: tuple[StellantisSensorEntityDescription, ...] = (
    StellantisSensorEntityDescription(
        key="battery_total_capacity",
        translation_key="battery_total_capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.battery.load.capacity",
    ),
    StellantisSensorEntityDescription(
        key="residual_electric_energy",
        translation_key="residual_electric_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.battery.load.residual",
    ),
    StellantisSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.battery.health.capacity",
    ),
    StellantisSensorEntityDescription(
        key="battery_resistance",
        translation_key="battery_resistance",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.battery.health.resistance",
    ),
    StellantisSensorEntityDescription(
        key="charging_status",
        translation_key="charging_status",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.charging.status",
    ),
    StellantisSensorEntityDescription(
        key="charging_remaining_time",
        translation_key="charging_remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.charging.remainingTime",
    ),
    StellantisSensorEntityDescription(
        key="charging_rate",
        translation_key="charging_rate",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.charging.chargingRate",
    ),
    StellantisSensorEntityDescription(
        key="charging_mode",
        translation_key="charging_mode",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.charging.chargingMode",
    ),
    StellantisSensorEntityDescription(
        key="next_charge",
        translation_key="next_charge",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_path="$.energies[?(@.type == 'Electric')].extension.electric.charging.nextDelayedTime",
    ),
)


THERMIC_ENGINE_EXTENSION_SENSORS: tuple[StellantisSensorEntityDescription, ...] = (
    StellantisSensorEntityDescription(
        key="thermic_engine_coolant_level",
        translation_key="thermic_engine_coolant_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path="$.engines[?(@.type == 'Thermic')].extension.thermic.coolant.level",
    ),
    StellantisSensorEntityDescription(
        key="thermic_engine_coolant_temperature",
        translation_key="thermic_engine_coolant_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_path="$.engines[?(@.type == 'Thermic')].extension.thermic.coolant.temp",
    ),
    StellantisSensorEntityDescription(
        key="thermic_engine_oil_level",
        translation_key="thermic_engine_oil_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_path="$.engines[?(@.type == 'Thermic')].extension.thermic.oil.level",
    ),
    StellantisSensorEntityDescription(
        key="thermic_engine_oil_temperature",
        translation_key="thermic_engine_oil_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_path="$.engines[?(@.type == 'Thermic')].extension.thermic.oil.temp",
    ),
    StellantisSensorEntityDescription(
        key="thermic_engine_air_temperature",
        translation_key="thermic_engine_air_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_path="$.engines[?(@.type == 'Thermic')].extension.thermic.air.temp",
    ),
)


SENSORS: tuple[StellantisSensorEntityDescription, ...] = (
    StellantisSensorEntityDescription(
        key="ignition",
        translation_key="ignition",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.ignition.type",
    ),
    StellantisSensorEntityDescription(
        key="powertrain_status",
        translation_key="powertrain_status",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.powertrain.status",
    ),
    StellantisSensorEntityDescription(
        key="doors_lock_state",
        translation_key="doors_lock_state",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.doorsState.lockedStates",
    ),
    StellantisSensorEntityDescription(
        key="privacy",
        translation_key="privacy",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.privacy.state",
    ),
    StellantisSensorEntityDescription(
        key="auxiliary_battery_health",
        translation_key="auxiliary_battery_health",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_path="$.battery.voltage",
    ),
    StellantisSensorEntityDescription(
        key="auto_e_call_triggering",
        translation_key="auto_e_call_triggering",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.safety.autoECallTriggering",
    ),
    StellantisSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value_path="$.odometer.mileage",
    ),
    StellantisSensorEntityDescription(
        key="acceleration",
        translation_key="acceleration",
        native_unit_of_measurement="m/s²",
        suggested_display_precision=1,
        value_path="$.kinetic.acceleration",
    ),
    StellantisSensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_path="$.kinetic.speed",
    ),
    StellantisSensorEntityDescription(
        key="environment_air_temperature",
        translation_key="environment_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_path="$.environment.air.temp",
    ),
    StellantisSensorEntityDescription(
        key="driving_mode",
        translation_key="driving_mode",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.drivingBehavior.mode",
    ),
)


PRECONDITIONING_SENSORS = (
    StellantisSensorEntityDescription(
        key="preconditioning_status",
        translation_key="preconditioning_status",
        device_class=SensorDeviceClass.ENUM,
        value_path="$.preconditioning.airConditioning.status",
    ),
)


def get_common_energy_sensors(
    energies: list[dict[str, Any]],
):
    """Get common sensors common to all energies."""
    for energy in energies:
        energy_type = energy["type"]
        yield StellantisSensorEntityDescription(
            key=f"{snakecase(energy_type)}_energy_level",
            translation_key=f"{snakecase(energy_type)}_energy_level",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            suggested_display_precision=1,
            value_path=f"$.energies[?(@.type == '{energy_type}')].level",
        )
        yield StellantisSensorEntityDescription(
            key=f"{snakecase(energy_type)}_energy_autonomy",
            translation_key=f"{snakecase(energy_type)}_energy_autonomy",
            device_class=SensorDeviceClass.DISTANCE,
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            value_path=f"$.energies[?(@.type == '{energy_type}')].autonomy",
        )


def get_fuel_energy_sensor(
    energy_sub_type: str,
) -> StellantisSensorEntityDescription:
    """Get the fuel instant consumption sensor with its correct native unit of measurement."""
    return StellantisSensorEntityDescription(
        key="fuel_instant_consumption",
        translation_key="fuel_instant_consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="L/100km"
        if energy_sub_type == "FossilEnergy"
        else "Kg/100Km"
        if energy_sub_type == "Hydrogen"
        else None,
        suggested_display_precision=1,
        value_path="$.energies.[?(@.type == 'Fuel')].extension.fuel.consumptions.instant",
    )


def get_engine_common_sensors(
    engines: list[dict[str, Any]],
):
    """Get common sensors common to all engines."""
    for engine in engines:
        engine_type = engine["type"]
        yield StellantisSensorEntityDescription(
            key=f"{snakecase(engine['type'])}_engine_speed",
            translation_key=f"{snakecase(engine['type'])}_engine_speed",
            value_path=f"$.engines[?(@.type == '{engine_type}')].speed",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis sensors."""

    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    for vehicle in data.coordinator.data:
        sensors = SENSORS
        sensors += tuple(
            get_common_energy_sensors(
                jsonpath(
                    vehicle.status,
                    "$.energies[*]",
                )
            )
        )
        sensors += tuple(
            get_engine_common_sensors(jsonpath(vehicle.status, "$.engines[*]"))
        )

        if jsonpath(
            vehicle.status,
            "$.preconditioning.airConditioning",
        ):
            sensors += PRECONDITIONING_SENSORS
            async_add_entities(
                StellantisPreconditioningProgramSensor(
                    data.coordinator,
                    vehicle,
                    StellantisPreconditioningSensorEntityDescription(
                        key=f"preconditioning_program_{slot}",
                        translation_key=f"preconditioning_program_{slot}",
                        device_class=SensorDeviceClass.TIMESTAMP,
                        slot=slot,
                    ),
                )
                for slot in range(1, 5)
            )

        if matches := jsonpath(
            vehicle.status,
            "$.energies[?(@.type == 'Fuel')]",
        ):
            sensors += (
                *FUEL_ENERGY_EXTENSION_SENSORS,
                get_fuel_energy_sensor(matches[0]["subType"]),
            )

        if jsonpath(
            vehicle.status,
            "$.energies[?(@.type == 'Electric')]",
        ):
            sensors += ELECTRIC_ENERGY_EXTENSION_SENSORS

        if jsonpath(
            vehicle.status,
            "$.engines[?(@.type == 'Thermic')]",
        ):
            sensors += THERMIC_ENGINE_EXTENSION_SENSORS

        async_add_entities(
            StellantisSensor(
                data.coordinator,
                vehicle,
                description,
            )
            for description in sensors
        )


class StellantisSensor(StellantisBaseEntity, SensorEntity):
    """Representation of a Stellantis sensor."""

    entity_description: StellantisSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate the sensor value from the entity description."""
        value = self.get_from_vehicle_status(self.entity_description.value_path)
        if value:
            if self.entity_description.key == "fuel_consumption":
                # Fuel consumption is in centiliters, convert it to liters
                return value / 100
            if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
                if (next_timestamp := get_next_timestamp(value)) is not None:
                    return next_timestamp
            if self.entity_description.device_class == SensorDeviceClass.DURATION:
                if (duration := dt_util.parse_duration(value)) is not None:
                    return duration.total_seconds()
            if self.entity_description.device_class == SensorDeviceClass.ENUM:
                # In order to use translation keys, we need to snake case the value
                # because Stellantis API returns values in pascal case
                return snakecase(value)
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.native_value is not None and super().available


class StellantisPreconditioningProgramSensor(StellantisBaseEntity, SensorEntity):
    """Representation of a Stellantis preconditioning sensor."""

    entity_description: StellantisPreconditioningSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate timestamp of the next time the preconditioning program will get activated."""
        program = self.get_from_vehicle_status(
            f"$.preconditioning.airConditioning.programs[?(@.slot == {self.entity_description.slot})]"
        )
        if not program:
            return None

        try:
            if not program["enabled"]:
                return None

            return get_next_timestamp_on_weekdays(
                program["start"],
                program["occurence"]["day"],  # codespell:ignore occurence
            )
        except KeyError:
            return None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        program = self.get_from_vehicle_status(
            f"$.preconditioning.airConditioning.programs[?(@.slot == {self.entity_description.slot})]"
        )
        if not program:
            return None

        return {
            "start": program["start"],
            "recurrence": program["recurrence"],
            "occurrence": program["occurence"],  # codespell:ignore occurence
        }

    @property
    def available(self) -> bool:
        """Return available if the program exists."""
        program = self.get_from_vehicle_status(
            f"$.preconditioning.airConditioning.programs[?(@.slot == {self.entity_description.slot})]"
        )
        return program and super().available


def get_next_timestamp(time_on_day: str) -> datetime | None:
    """Get the next time on the day that have not passed yet.

    If the current time has already passed today, it will return the time for tomorrow.
    """
    if (duration := dt_util.parse_duration(time_on_day)) is None:
        return None
    next_time = dt_util.start_of_local_day() + duration

    if dt_util.now() > next_time:
        next_time = next_time + timedelta(days=1)

    return next_time


def get_next_timestamp_on_weekdays(
    time_on_day: str, weekdays: list[str]
) -> datetime | None:
    """Get the nearest timestamp for the given weekdays and time that is in the future."""
    if not weekdays:
        return None

    weekdays_numbers = [WEEKDAYS.index(day.lower()) for day in weekdays]
    now = dt_util.now()
    current_day = now.weekday()

    if (duration := dt_util.parse_duration(time_on_day)) is None:
        return None

    if current_day in weekdays_numbers:
        next_time = dt_util.start_of_local_day() + duration
        if now < next_time:
            return next_time

    for i in range(1, 8):
        next_day = (current_day + i) % 7
        if next_day in weekdays_numbers:
            return dt_util.start_of_local_day() + timedelta(days=i) + duration
    return None

