"""Stellantis sensor platform."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from stellantis.model import EnergySubType, EnergyType, EngineType, Status, WeekDays

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, StateType, UndefinedType
from homeassistant.util import dt as dt_util, slugify

from .coordinator import StellantisConfigEntry
from .entity import (
    StellantisBaseEntity,
    StellantisEntityDescription,
    StellantisPreconditioningEntity,
)

WEEK_DAYS_LIST = list(WeekDays.__members__.values())


@dataclass(frozen=True, kw_only=True)
class StellantisSensorEntityDescription(
    StellantisEntityDescription, SensorEntityDescription
):
    """Describes Stellantis sensor entity."""


FUEL_ENERGY_EXTENSION_SENSORS: tuple[StellantisSensorEntityDescription, ...] = (
    StellantisSensorEntityDescription(
        key="fuel_consumption",
        translation_key="fuel_consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=4,
        value_fn=lambda status: consumptions.total
        if (
            energy := next(
                (
                    energy
                    for energy in (status.energies or [])
                    if energy.type == EnergyType.FUEL
                ),
                None,
            )
        )
        and (extension := energy.extension)
        and (fuel := extension.fuel)
        and (consumptions := fuel.consumptions)
        else UNDEFINED,
    ),
)


ELECTRIC_ENERGY_EXTENSION_SENSORS: tuple[StellantisSensorEntityDescription, ...] = (
    StellantisSensorEntityDescription(
        key="battery_total_capacity",
        translation_key="battery_total_capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda status: load.capacity
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
        and (battery := electric.battery)
        and (load := battery.load)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="residual_electric_energy",
        translation_key="residual_electric_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda status: load.residual
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
        and (battery := electric.battery)
        and (load := battery.load)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda status: health.capacity
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
        and (battery := electric.battery)
        and (health := battery.health)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="battery_resistance",
        translation_key="battery_resistance",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda status: health.resistance
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
        and (battery := electric.battery)
        and (health := battery.health)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="charging_status",
        translation_key="charging_status",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda status: charging.status
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
    StellantisSensorEntityDescription(
        key="charging_remaining_time",
        translation_key="charging_remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda status: charging.remaining_time
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
    StellantisSensorEntityDescription(
        key="charging_rate",
        translation_key="charging_rate",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda status: charging.charging_rate
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
    StellantisSensorEntityDescription(
        key="charging_mode",
        translation_key="charging_mode",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda status: charging.charging_mode
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
    StellantisSensorEntityDescription(
        key="next_charge",
        translation_key="next_charge",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda status: charging.next_delayed_time
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


THERMIC_ENGINE_EXTENSION_SENSORS: tuple[StellantisSensorEntityDescription, ...] = (
    StellantisSensorEntityDescription(
        key="thermic_engine_coolant_level",
        translation_key="thermic_engine_coolant_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda status: coolant.level
        if (
            engine := next(
                (
                    engine
                    for engine in (status.engines or [])
                    if engine.type == EngineType.THERMIC
                ),
                None,
            )
        )
        and (extension := engine.extension)
        and (thermic := extension.thermic)
        and (coolant := thermic.coolant)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="thermic_engine_coolant_temperature",
        translation_key="thermic_engine_coolant_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda status: coolant.temp
        if (
            engine := next(
                (
                    engine
                    for engine in (status.engines or [])
                    if engine.type == EngineType.THERMIC
                ),
                None,
            )
        )
        and (extension := engine.extension)
        and (thermic := extension.thermic)
        and (coolant := thermic.coolant)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="thermic_engine_oil_level",
        translation_key="thermic_engine_oil_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda status: oil.level
        if (
            engine := next(
                (
                    engine
                    for engine in (status.engines or [])
                    if engine.type == EngineType.THERMIC
                ),
                None,
            )
        )
        and (extension := engine.extension)
        and (thermic := extension.thermic)
        and (oil := thermic.oil)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="thermic_engine_oil_temperature",
        translation_key="thermic_engine_oil_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda status: oil.temp
        if (
            engine := next(
                (
                    engine
                    for engine in (status.engines or [])
                    if engine.type == EngineType.THERMIC
                ),
                None,
            )
        )
        and (extension := engine.extension)
        and (thermic := extension.thermic)
        and (oil := thermic.oil)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="thermic_engine_air_temperature",
        translation_key="thermic_engine_air_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda status: air.temp
        if (
            engine := next(
                (
                    engine
                    for engine in (status.engines or [])
                    if engine.type == EngineType.THERMIC
                ),
                None,
            )
        )
        and (extension := engine.extension)
        and (thermic := extension.thermic)
        and (air := thermic.air)
        else UNDEFINED,
    ),
)


SENSORS: tuple[StellantisSensorEntityDescription, ...] = (
    StellantisSensorEntityDescription(
        key="ignition",
        translation_key="ignition",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda status: status.ignition.type if status.ignition else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="powertrain_status",
        translation_key="powertrain_status",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda status: status.powertrain.status
        if status.powertrain
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="privacy",
        translation_key="privacy",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda status: status.privacy.state if status.privacy else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="auxiliary_battery_health",
        translation_key="auxiliary_battery_health",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda status: status.battery.voltage if status.battery else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="auto_e_call_triggering",
        translation_key="auto_e_call_triggering",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda status: status.safety.auto_e_call_triggering
        if status.safety
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        value_fn=lambda status: status.odometer.mileage
        if status.odometer
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="acceleration",
        translation_key="acceleration",
        native_unit_of_measurement="m/s²",
        suggested_display_precision=1,
        value_fn=lambda status: status.kinetic.acceleration
        if status.kinetic
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=lambda status: status.kinetic.speed if status.kinetic else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="environment_air_temperature",
        translation_key="environment_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda status: air.temp
        if (environment := status.environment) and (air := environment.air)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="driving_mode",
        translation_key="driving_mode",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda status: status.driving_behavior.mode
        if status.driving_behavior
        else UNDEFINED,
    ),
)


PRECONDITIONING_SENSORS = (
    StellantisSensorEntityDescription(
        key="preconditioning_status",
        translation_key="preconditioning_status",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda status: air_conditioning.status
        if (preconditioning := status.preconditioning)
        and (air_conditioning := preconditioning.air_conditioning)
        else UNDEFINED,
    ),
)


def _make_energy_level_fn(
    energy_type: EnergyType,
) -> Callable[[Status], StateType | UndefinedType]:
    def energy_level_fn(status: Status) -> StateType | UndefinedType:
        for energy in status.energies or []:
            if energy.type == energy_type:
                return energy.level
        return UNDEFINED

    return energy_level_fn


def _make_energy_autonomy_fn(
    energy_type: EnergyType,
) -> Callable[[Status], StateType | UndefinedType]:
    def energy_autonomy_fn(status: Status) -> StateType | UndefinedType:
        for energy in status.energies or []:
            if energy.type == energy_type:
                return energy.autonomy
        return UNDEFINED

    return energy_autonomy_fn


COMMON_ENERGY_SENSORS = {
    energy_type: (
        StellantisSensorEntityDescription(
            key=f"{slugify(energy_type)}_energy_level",
            translation_key=f"{slugify(energy_type)}_energy_level",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            suggested_display_precision=1,
            value_fn=_make_energy_level_fn(energy_type),
        ),
        StellantisSensorEntityDescription(
            key=f"{slugify(energy_type)}_energy_autonomy",
            translation_key=f"{slugify(energy_type)}_energy_autonomy",
            device_class=SensorDeviceClass.DISTANCE,
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            suggested_display_precision=1,
            value_fn=_make_energy_autonomy_fn(energy_type),
        ),
    )
    for energy_type in EnergyType.__members__.values()
}


def _make_fuel_instant_consumption_fn(
    energy_sub_type: EnergySubType | None,
) -> Callable[[Status], StateType | UndefinedType]:
    def fuel_instant_consumption_fn(status: Status) -> StateType | UndefinedType:
        for energy in status.energies or []:
            if (
                energy.sub_type == energy_sub_type
                and (extension := energy.extension)
                and (fuel := extension.fuel)
                and (consumptions := fuel.consumptions)
            ):
                return consumptions.instant
        return UNDEFINED

    return fuel_instant_consumption_fn


FUEL_ENERGY_SENSORS_MAP = {
    energy_sub_type: StellantisSensorEntityDescription(
        key="fuel_instant_consumption",
        translation_key="fuel_instant_consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=native_unit_of_measurement,
        suggested_display_precision=1,
        value_fn=_make_fuel_instant_consumption_fn(energy_sub_type),
    )
    for energy_sub_type, native_unit_of_measurement in (
        (EnergySubType.FOSSIL_ENERGY, "L/100km"),
        (EnergySubType.HYDROGEN, "Kg/100Km"),
        (None, None),
    )
}


def _make_engine_speed_fn(
    engine_type: EngineType,
) -> Callable[[Status], StateType | UndefinedType]:
    def engine_speed_fn(status: Status) -> StateType | UndefinedType:
        for engine in status.engines or []:
            if engine.type == engine_type:
                return engine.speed
        return UNDEFINED

    return engine_speed_fn


ENGINE_SENSORS_MAP = {
    engine_type: StellantisSensorEntityDescription(
        key=f"{slugify(engine_type)}_engine_speed",
        translation_key=f"{slugify(engine_type)}_engine_speed",
        value_fn=_make_engine_speed_fn(engine_type),
    )
    for engine_type in EngineType.__members__.values()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis sensors."""
    entities: list[StellantisBaseEntity] = []
    for vehicle_coordinator in entry.runtime_data:
        sensors: list[StellantisSensorEntityDescription] = []

        if (
            vehicle_coordinator.data.preconditioning
            and vehicle_coordinator.data.preconditioning.air_conditioning
        ):
            sensors += PRECONDITIONING_SENSORS

            slots = 4  # By default, we assume 4 slots
            if (
                (embedded := vehicle_coordinator.vehicle.embedded)
                and embedded.extension
                and embedded.extension.onboard_capabilities
                and (remote := embedded.extension.onboard_capabilities.remote)
                and remote.preconditioning.supported
                and (programs := remote.preconditioning.parameters.programs)
            ):
                slots = programs.size
            entities.extend(
                StellantisPreconditioningProgramSensor(
                    hass,
                    vehicle_coordinator,
                    StellantisSensorEntityDescription(
                        key=f"preconditioning_program_{slot}",
                        translation_key="preconditioning_program",
                        translation_placeholders={"slot": str(slot)},
                        device_class=SensorDeviceClass.TIMESTAMP,
                        value_fn=lambda _: None,
                    ),
                    entry,
                    slot,
                )
                for slot in range(1, slots + 1)
            )

        for energy in vehicle_coordinator.data.energies or []:
            if energy.type:
                sensors.extend(COMMON_ENERGY_SENSORS[energy.type])
            match energy.type:
                case EnergyType.FUEL:
                    sensors += [
                        *FUEL_ENERGY_EXTENSION_SENSORS,
                        FUEL_ENERGY_SENSORS_MAP[energy.sub_type],
                    ]
                case EnergyType.ELECTRIC:
                    sensors += ELECTRIC_ENERGY_EXTENSION_SENSORS

        for engines in vehicle_coordinator.data.engines or []:
            if engines.type:
                sensors.append(ENGINE_SENSORS_MAP[engines.type])
                if engines.type == EngineType.THERMIC:
                    sensors += THERMIC_ENGINE_EXTENSION_SENSORS

        entities.extend(
            StellantisSensor(
                vehicle_coordinator,
                description,
            )
            for description in list(SENSORS) + sensors
        )

    async_add_entities(entities)


class StellantisSensor(StellantisBaseEntity, SensorEntity):
    """Representation of a Stellantis sensor."""

    entity_description: StellantisSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime | None:
        """Calculate the sensor value from the entity description."""
        if self.status_value and self.status_value != UNDEFINED:
            if self.entity_description.key == "fuel_consumption":
                assert isinstance(self.status_value, float)
                # Fuel consumption is in centiliters, convert it to liters
                return self.status_value / 100
            match self.entity_description.device_class:
                case SensorDeviceClass.TIMESTAMP:
                    assert isinstance(self.status_value, str)
                    if (
                        next_timestamp := _get_next_timestamp(self.status_value)
                    ) is not None:
                        return next_timestamp
                case SensorDeviceClass.DURATION:
                    assert isinstance(self.status_value, str)
                    if (
                        duration := dt_util.parse_duration(self.status_value)
                    ) is not None:
                        return duration.total_seconds()
                case SensorDeviceClass.ENUM:
                    assert isinstance(self.status_value, str)
                    return slugify(self.status_value)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.native_value is not None and super().available


class StellantisPreconditioningProgramSensor(
    StellantisPreconditioningEntity[None], SensorEntity
):
    """Representation of a Stellantis preconditioning sensor."""

    entity_description: StellantisSensorEntityDescription

    def _handle_update_from_successful_remote_action(self, state: None) -> None:
        pass

    @property
    def native_value(self) -> datetime | None:
        """Calculate timestamp of the next time the preconditioning program will get activated."""
        return (
            _get_next_timestamp_on_weekdays(
                self.program.start,
                self.program.occurence.day  # codespell:ignore occurence
                if self.program.occurence  # codespell:ignore occurence
                else None,
            )
            if self.program != UNDEFINED
            else None
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""

        return {
            "start": self.program.start
            if self.program and self.program != UNDEFINED
            else None,
            "recurrence": self.program.recurrence
            if self.program and self.program != UNDEFINED
            else None,
            "occurrence": self.program.occurence  # codespell:ignore occurence
            if self.program and self.program != UNDEFINED
            else None,
        }


def _get_next_timestamp(time_on_day: str) -> datetime | None:
    """Get the next time on the day that have not passed yet.

    If the current time has already passed today, it will return the time for tomorrow.
    """
    if (duration := dt_util.parse_duration(time_on_day)) is None:
        return None
    next_time = dt_util.start_of_local_day() + duration

    if dt_util.now() > next_time:
        next_time = next_time + timedelta(days=1)

    return next_time


def _get_next_timestamp_on_weekdays(
    time_on_day: str, weekdays: list[WeekDays] | None
) -> datetime | None:
    """Get the nearest timestamp for the given weekdays and time that is in the future."""
    if not weekdays:
        return None

    weekdays_numbers = [WEEK_DAYS_LIST.index(day) for day in weekdays]
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
