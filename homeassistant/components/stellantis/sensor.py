"""Stellantis sensor platform."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from stellantis.model import (
    AirConditioningStatus,
    AutoECallTriggering,
    ChargingMode,
    ChargingStatusEnum,
    DrivingMode,
    EnergySubType,
    EnergyType,
    EngineType,
    IgnitionType,
    OnboardCapabilitiesEnum,
    PowertrainStatus,
    PrivacyState,
    Status,
    WeekDays,
)

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED, StateType, UndefinedType
from homeassistant.util import dt as dt_util, slugify

from .coordinator import StellantisConfigEntry
from .entity import StellantisBaseEntity, StellantisEntityDescription
from .helpers import get_energy, get_engine

WEEK_DAYS_LIST = list(WeekDays.__members__.values())


@dataclass(frozen=True, kw_only=True)
class StellantisSensorEntityDescription(
    StellantisEntityDescription, SensorEntityDescription
):
    """Describes Stellantis sensor entity."""

    scope: OnboardCapabilitiesEnum


FUEL_ENERGY_EXTENSION_SENSORS = (
    StellantisSensorEntityDescription(
        key="fuel_total_consumption",
        translation_key="fuel_total_consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=4,
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: consumptions.total
        if (energy := get_energy(status, EnergyType.FUEL))
        and (extension := energy.extension)
        and (fuel := extension.fuel)
        and (consumptions := fuel.consumptions)
        else UNDEFINED,
    ),
)


ELECTRIC_ENERGY_EXTENSION_SENSORS = (
    StellantisSensorEntityDescription(
        key="battery_total_capacity",
        translation_key="battery_total_capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: load.capacity
        if (energy := get_energy(status, EnergyType.ELECTRIC))
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: load.residual
        if (energy := get_energy(status, EnergyType.ELECTRIC))
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: health.capacity
        if (energy := get_energy(status, EnergyType.ELECTRIC))
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: health.resistance
        if (energy := get_energy(status, EnergyType.ELECTRIC))
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
        options=[
            slugify(charging_status)
            for charging_status in ChargingStatusEnum.__members__.values()
        ],
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: charging.status
        if (energy := get_energy(status, EnergyType.ELECTRIC))
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: charging.remaining_time
        if (energy := get_energy(status, EnergyType.ELECTRIC))
        and (extension := energy.extension)
        and (electric := extension.electric)
        and (charging := electric.charging)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="charging_rate",
        translation_key="charging_rate",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: charging.charging_rate
        if (energy := get_energy(status, EnergyType.ELECTRIC))
        and (extension := energy.extension)
        and (electric := extension.electric)
        and (charging := electric.charging)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="charging_mode",
        translation_key="charging_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[
            slugify(charging_mode)
            for charging_mode in ChargingMode.__members__.values()
        ],
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: charging.charging_mode
        if (energy := get_energy(status, EnergyType.ELECTRIC))
        and (extension := energy.extension)
        and (electric := extension.electric)
        and (charging := electric.charging)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="next_charge",
        translation_key="next_charge",
        device_class=SensorDeviceClass.TIMESTAMP,
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
        value_fn=lambda status: charging.next_delayed_time
        if (energy := get_energy(status, EnergyType.ELECTRIC))
        and (extension := energy.extension)
        and (electric := extension.electric)
        and (charging := electric.charging)
        else UNDEFINED,
    ),
)


THERMIC_ENGINE_EXTENSION_SENSORS = (
    StellantisSensorEntityDescription(
        key="thermic_engine_coolant_level",
        translation_key="thermic_engine_coolant_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENGINES,
        value_fn=lambda status: coolant.level
        if (engine := get_engine(status, EngineType.THERMIC))
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENGINES,
        value_fn=lambda status: coolant.temp
        if (engine := get_engine(status, EngineType.THERMIC))
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENGINES,
        value_fn=lambda status: oil.level
        if (engine := get_engine(status, EngineType.THERMIC))
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENGINES,
        value_fn=lambda status: oil.temp
        if (engine := get_engine(status, EngineType.THERMIC))
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENGINES,
        value_fn=lambda status: air.temp
        if (engine := get_engine(status, EngineType.THERMIC))
        and (extension := engine.extension)
        and (thermic := extension.thermic)
        and (air := thermic.air)
        else UNDEFINED,
    ),
)


SENSORS = (
    StellantisSensorEntityDescription(
        key="ignition",
        translation_key="ignition",
        device_class=SensorDeviceClass.ENUM,
        options=[slugify(ignition) for ignition in IgnitionType.__members__.values()],
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_IGNITION,
        value_fn=lambda status: status.ignition.type if status.ignition else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="powertrain_status",
        translation_key="powertrain_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            slugify(powertrain) for powertrain in PowertrainStatus.__members__.values()
        ],
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_POWERTRAIN,
        value_fn=lambda status: status.powertrain.status
        if status.powertrain
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="privacy",
        translation_key="privacy",
        device_class=SensorDeviceClass.ENUM,
        options=[
            slugify(privacy_state)
            for privacy_state in PrivacyState.__members__.values()
        ],
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_PRIVACY,
        value_fn=lambda status: status.privacy.state if status.privacy else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="auxiliary_battery_health",
        translation_key="auxiliary_battery_health",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_BATTERY,
        value_fn=lambda status: status.battery.voltage if status.battery else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="auto_e_call_triggering",
        translation_key="auto_e_call_triggering",
        device_class=SensorDeviceClass.ENUM,
        options=[
            slugify(auto_e_call)
            for auto_e_call in AutoECallTriggering.__members__.values()
        ],
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_SAFETY,
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ODOMETER,
        value_fn=lambda status: status.odometer.mileage
        if status.odometer
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="acceleration",
        translation_key="acceleration",
        native_unit_of_measurement="m/s²",
        suggested_display_precision=1,
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_KINETIC,
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_KINETIC,
        value_fn=lambda status: status.kinetic.speed if status.kinetic else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="environment_air_temperature",
        translation_key="environment_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_ENVIRONMENT,
        value_fn=lambda status: air.temp
        if (environment := status.environment) and (air := environment.air)
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="driving_mode",
        translation_key="driving_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[
            slugify(driving_mode) for driving_mode in DrivingMode.__members__.values()
        ],
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_DRIVING_BEHAVIOR,
        value_fn=lambda status: status.driving_behavior.mode
        if status.driving_behavior
        else UNDEFINED,
    ),
    StellantisSensorEntityDescription(
        key="preconditioning_status",
        translation_key="preconditioning_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            slugify(air_conditioning_status)
            for air_conditioning_status in AirConditioningStatus.__members__.values()
        ],
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_PRECONDITIONING,
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
            key=f"{energy_name.lower()}_energy_level",
            translation_key=f"{energy_name.lower()}_energy_level",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            suggested_display_precision=1,
            scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
            value_fn=_make_energy_level_fn(energy_type),
        ),
        StellantisSensorEntityDescription(
            key=f"{energy_name.lower()}_energy_autonomy",
            translation_key=f"{energy_name.lower()}_energy_autonomy",
            device_class=SensorDeviceClass.DISTANCE,
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            suggested_display_precision=1,
            scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
            value_fn=_make_energy_autonomy_fn(energy_type),
        ),
    )
    for energy_name, energy_type in EnergyType.__members__.items()
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
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES,
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
        key=f"{engine_name.lower()}_engine_speed",
        translation_key=f"{engine_name.lower()}_engine_speed",
        scope=OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENGINES,
        value_fn=_make_engine_speed_fn(engine_type),
    )
    for engine_name, engine_type in EngineType.__members__.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis sensors."""
    entities: list[StellantisBaseEntity] = []
    for vehicle_coordinator in entry.runtime_data.vehicle_coordinators:
        sensors: list[StellantisSensorEntityDescription] = []

        onboard_capabilities_data = (
            vehicle_coordinator.vehicle.embedded.extension.onboard_capabilities.data
            if vehicle_coordinator.vehicle.embedded
            and vehicle_coordinator.vehicle.embedded.extension
            and vehicle_coordinator.vehicle.embedded.extension.onboard_capabilities
            else None
        )

        if (
            onboard_capabilities_data is None
            or OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES
            in onboard_capabilities_data
        ):
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

        if (
            onboard_capabilities_data is None
            or OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENGINES
            in onboard_capabilities_data
        ):
            for engines in vehicle_coordinator.data.engines or []:
                if engines.type:
                    sensors.append(ENGINE_SENSORS_MAP[engines.type])
                    if engines.type == EngineType.THERMIC:
                        sensors += THERMIC_ENGINE_EXTENSION_SENSORS

        entities.extend(
            StellantisSensor(
                vehicle_coordinator, description, onboard_capabilities_data is None
            )
            for description in list(SENSORS) + sensors
            if onboard_capabilities_data is None
            or description.scope in onboard_capabilities_data
        )

    async_add_entities(entities)


class StellantisSensor(StellantisBaseEntity, SensorEntity):
    """Representation of a Stellantis sensor."""

    entity_description: StellantisSensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_available = True
        status_value = self.status_value

        if status_value is None or status_value == UNDEFINED:
            self._attr_native_value = None
            if status_value == UNDEFINED:
                self._attr_available = False

        elif self.entity_description.key == "fuel_total_consumption":
            assert isinstance(status_value, float)
            # Fuel consumption is in centiliters, convert it to liters
            self._attr_native_value = status_value / 100

        else:
            match self.entity_description.device_class:
                case SensorDeviceClass.TIMESTAMP:
                    assert isinstance(status_value, str)
                    self._attr_native_value = get_next_timestamp(status_value)
                case SensorDeviceClass.DURATION:
                    assert isinstance(status_value, str)
                    duration = dt_util.parse_duration(status_value)
                    self._attr_native_value = (
                        duration.total_seconds() if duration is not None else None
                    )
                case SensorDeviceClass.ENUM:
                    assert isinstance(status_value, str)
                    self._attr_native_value = slugify(status_value)
                case _:
                    self._attr_native_value = status_value
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available and super().available


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
