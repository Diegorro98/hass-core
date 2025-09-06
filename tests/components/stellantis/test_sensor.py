"""Test Stellantis sensor platform."""

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from stellantis.model import (
    AirConditioningStatus,
    AutoECallTriggering,
    ChargingMode,
    ChargingStatusEnum,
    DrivingMode,
    IgnitionType,
    PowertrainStatus,
    PrivacyState,
    Status,
    WeekDays,
)
from stellantis.model.error import StellantisError

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

TEST_TIMEZONE = ZoneInfo("US/Pacific")


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.freeze_time(
    datetime(2025, 9, 1, 12, 00, tzinfo=TEST_TIMEZONE).astimezone(UTC).isoformat()
)
@pytest.mark.parametrize(
    ("entity_id", "expected_updated_state", "update_status_value_fn"),
    [
        (
            "sensor.peugeot_suv_3008_fuel_total_consumption",
            "1773.3019",
            lambda status: setattr(
                status.energies[0].extension.fuel.consumptions, "total", 177330.19
            ),
        ),
        (
            "sensor.peugeot_suv_3008_fuel_total_consumption",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[0].extension.fuel.consumptions, "total", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_fuel_total_consumption",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[0].extension.fuel, "consumptions", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_total_capacity",
            "13200",
            lambda status: setattr(
                status.energies[1].extension.electric.battery.load, "capacity", 13200
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_total_capacity",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.battery.load, "capacity", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_total_capacity",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.battery, "load", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_residual_electric_energy",
            "5",
            lambda status: setattr(
                status.energies[1].extension.electric.battery.load, "residual", 5
            ),
        ),
        (
            "sensor.peugeot_suv_3008_residual_electric_energy",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.battery.load, "residual", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_residual_electric_energy",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.battery, "load", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_capacity",
            "90",
            lambda status: setattr(
                status.energies[1].extension.electric.battery.health, "capacity", 90
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_capacity",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.battery.health, "capacity", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_capacity",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.battery, "health", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_resistance",
            "80",
            lambda status: setattr(
                status.energies[1].extension.electric.battery.health, "resistance", 80
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_resistance",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.battery.health, "resistance", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_battery_resistance",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.battery, "health", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_status",
            "inprogress",
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.IN_PROGRESS,
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_status",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging, "status", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_status",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric, "charging", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_remaining_time",
            "3600.0",
            lambda status: setattr(
                status.energies[1].extension.electric.charging, "remaining_time", "PT1H"
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_remaining_time",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging, "remaining_time", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_remaining_time",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "remaining_time",
                "BAD_FORMAT",
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_remaining_time",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric, "charging", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_speed",
            "600",
            lambda status: setattr(
                status.energies[1].extension.electric.charging, "charging_rate", 600
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_speed",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging, "charging_rate", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_speed",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric, "charging", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_mode",
            "quick",
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "charging_mode",
                ChargingMode.QUICK,
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_mode",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging, "charging_mode", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_charging_mode",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric, "charging", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_next_charge",
            datetime(2025, 9, 2, 9, 30, tzinfo=TEST_TIMEZONE)
            .astimezone(UTC)
            .isoformat(),
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "next_delayed_time",
                "PT9H30M",
            ),
        ),
        (
            "sensor.peugeot_suv_3008_next_charge",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "next_delayed_time",
                "BAD_FORMAT",
            ),
        ),
        (
            "sensor.peugeot_suv_3008_next_charge",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "next_delayed_time",
                None,
            ),
        ),
        (
            "sensor.peugeot_suv_3008_next_charge",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric, "charging", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_coolant_level",
            "80",
            lambda status: setattr(
                status.engines[0].extension.thermic.coolant, "level", 80
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_coolant_level",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.engines[0].extension.thermic.coolant, "level", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_coolant_level",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.engines[0].extension.thermic, "coolant", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_coolant_temperature",
            "90.0",
            lambda status: setattr(
                status.engines[0].extension.thermic.coolant, "temp", 90.0
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_coolant_temperature",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.engines[0].extension.thermic.coolant, "temp", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_coolant_temperature",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.engines[0].extension.thermic, "coolant", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_oil_level",
            "90",
            lambda status: setattr(
                status.engines[0].extension.thermic.oil, "level", 90
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_oil_level",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.engines[0].extension.thermic.oil, "level", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_oil_level",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.engines[0].extension.thermic, "oil", None),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_oil_temperature",
            "80.0",
            lambda status: setattr(
                status.engines[0].extension.thermic.oil, "temp", 80.0
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_oil_temperature",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.engines[0].extension.thermic.oil, "temp", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_oil_temperature",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.engines[0].extension.thermic, "oil", None),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_air_temperature",
            "25.0",
            lambda status: setattr(
                status.engines[0].extension.thermic.air, "temp", 25.0
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_air_temperature",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.engines[0].extension.thermic.air, "temp", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_air_temperature",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.engines[0].extension.thermic, "air", None),
        ),
        (
            "sensor.peugeot_suv_3008_ignition",
            "start",
            lambda status: setattr(status.ignition, "type", IgnitionType.START),
        ),
        (
            "sensor.peugeot_suv_3008_ignition",
            STATE_UNKNOWN,
            lambda status: setattr(status.ignition, "type", None),
        ),
        (
            "sensor.peugeot_suv_3008_ignition",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "ignition", None),
        ),
        (
            "sensor.peugeot_suv_3008_powertrain_status",
            "running",
            lambda status: setattr(
                status.powertrain, "status", PowertrainStatus.RUNNING
            ),
        ),
        (
            "sensor.peugeot_suv_3008_powertrain_status",
            STATE_UNKNOWN,
            lambda status: setattr(status.powertrain, "status", None),
        ),
        (
            "sensor.peugeot_suv_3008_powertrain_status",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "powertrain", None),
        ),
        (
            "sensor.peugeot_suv_3008_privacy",
            "full",
            lambda status: setattr(status.privacy, "state", PrivacyState.FULL),
        ),
        (
            "sensor.peugeot_suv_3008_privacy",
            STATE_UNKNOWN,
            lambda status: setattr(status.privacy, "state", None),
        ),
        (
            "sensor.peugeot_suv_3008_privacy",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "privacy", None),
        ),
        (
            "sensor.peugeot_suv_3008_auxiliary_battery_health",
            "98.5",
            lambda status: setattr(status.battery, "voltage", 98.5),
        ),
        (
            "sensor.peugeot_suv_3008_auxiliary_battery_health",
            STATE_UNKNOWN,
            lambda status: setattr(status.battery, "voltage", None),
        ),
        (
            "sensor.peugeot_suv_3008_auxiliary_battery_health",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "battery", None),
        ),
        (
            "sensor.peugeot_suv_3008_auto_e_call_triggering",
            "detected",
            lambda status: setattr(
                status.safety, "auto_e_call_triggering", AutoECallTriggering.DETECTED
            ),
        ),
        (
            "sensor.peugeot_suv_3008_auto_e_call_triggering",
            STATE_UNKNOWN,
            lambda status: setattr(status.safety, "auto_e_call_triggering", None),
        ),
        (
            "sensor.peugeot_suv_3008_auto_e_call_triggering",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "safety", None),
        ),
        (
            "sensor.peugeot_suv_3008_mileage",
            "13000",
            lambda status: setattr(status.odometer, "mileage", 13000),
        ),
        (
            "sensor.peugeot_suv_3008_mileage",
            STATE_UNKNOWN,
            lambda status: setattr(status.odometer, "mileage", None),
        ),
        (
            "sensor.peugeot_suv_3008_mileage",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "odometer", None),
        ),
        (
            "sensor.peugeot_suv_3008_acceleration",
            "2.5",
            lambda status: setattr(status.kinetic, "acceleration", 2.5),
        ),
        (
            "sensor.peugeot_suv_3008_acceleration",
            STATE_UNKNOWN,
            lambda status: setattr(status.kinetic, "acceleration", None),
        ),
        (
            "sensor.peugeot_suv_3008_acceleration",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "kinetic", None),
        ),
        (
            "sensor.peugeot_suv_3008_speed",
            "80.0",
            lambda status: setattr(status.kinetic, "speed", 80.0),
        ),
        (
            "sensor.peugeot_suv_3008_speed",
            STATE_UNKNOWN,
            lambda status: setattr(status.kinetic, "speed", None),
        ),
        (
            "sensor.peugeot_suv_3008_speed",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "kinetic", None),
        ),
        (
            "sensor.peugeot_suv_3008_environment_air_temperature",
            "25.5",
            lambda status: setattr(status.environment.air, "temp", 25.5),
        ),
        (
            "sensor.peugeot_suv_3008_environment_air_temperature",
            STATE_UNKNOWN,
            lambda status: setattr(status.environment.air, "temp", None),
        ),
        (
            "sensor.peugeot_suv_3008_environment_air_temperature",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.environment, "air", None),
        ),
        (
            "sensor.peugeot_suv_3008_driving_mode",
            "eco",
            lambda status: setattr(status.driving_behavior, "mode", DrivingMode.ECO),
        ),
        (
            "sensor.peugeot_suv_3008_driving_mode",
            STATE_UNKNOWN,
            lambda status: setattr(status.driving_behavior, "mode", None),
        ),
        (
            "sensor.peugeot_suv_3008_driving_mode",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "driving_behavior", None),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_status",
            "enabled",
            lambda status: setattr(
                status.preconditioning.air_conditioning,
                "status",
                AirConditioningStatus.ENABLED,
            ),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_status",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.preconditioning.air_conditioning, "status", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_status",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.preconditioning, "air_conditioning", None),
        ),
        (
            "sensor.peugeot_suv_3008_fuel_energy_level",
            "80.0",
            lambda status: setattr(status.energies[0], "level", 80.0),
        ),
        (
            "sensor.peugeot_suv_3008_fuel_energy_level",
            STATE_UNKNOWN,
            lambda status: setattr(status.energies[0], "level", None),
        ),
        (
            "sensor.peugeot_suv_3008_fuel_energy_level",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "energies", None),
        ),
        (
            "sensor.peugeot_suv_3008_electric_energy_autonomy",
            "40.0",
            lambda status: setattr(status.energies[1], "autonomy", 40.0),
        ),
        (
            "sensor.peugeot_suv_3008_electric_energy_autonomy",
            STATE_UNKNOWN,
            lambda status: setattr(status.energies[1], "autonomy", None),
        ),
        (
            "sensor.peugeot_suv_3008_electric_energy_autonomy",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "energies", None),
        ),
        (
            "sensor.peugeot_suv_3008_fuel_instant_consumption",
            "80.0",
            lambda status: setattr(
                status.energies[0].extension.fuel.consumptions, "instant", 80.0
            ),
        ),
        (
            "sensor.peugeot_suv_3008_fuel_instant_consumption",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[0].extension.fuel.consumptions, "instant", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_fuel_instant_consumption",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[0].extension.fuel, "consumptions", None
            ),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_speed",
            "80.0",
            lambda status: setattr(status.engines[0], "speed", 80.0),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_speed",
            STATE_UNKNOWN,
            lambda status: setattr(status.engines[0], "speed", None),
        ),
        (
            "sensor.peugeot_suv_3008_thermic_engine_speed",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "engines", None),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_program_1",
            datetime(2025, 9, 1, 15, 0, tzinfo=TEST_TIMEZONE)
            .astimezone(UTC)
            .isoformat(),
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[0], "start", "PT15H"
            ),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_program_1",
            datetime(2025, 9, 8, 9, 30, tzinfo=TEST_TIMEZONE)
            .astimezone(UTC)
            .isoformat(),
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[0], "start", "PT9H30M"
            ),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_program_1",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[0],
                "start",
                "BAD_FORMAT",
            ),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_program_1",
            datetime(2025, 9, 2, 14, 30, tzinfo=TEST_TIMEZONE)
            .astimezone(UTC)
            .isoformat(),
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[
                    0
                ].occurence,  # codespell:ignore occurence
                "day",
                [WeekDays.TUESDAY],
            ),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_program_1",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[
                    0
                ].occurence,  # codespell:ignore occurence
                "day",
                None,
            ),
        ),
        (
            "sensor.peugeot_suv_3008_preconditioning_program_1",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.preconditioning.air_conditioning, "programs", None
            ),
        ),
    ],
)
async def test_sensor_state_and_updates(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_status: Status,
    entity_id: str,
    expected_updated_state: str,
    update_status_value_fn: Callable[[Status], None],
) -> None:
    """Test Stellantis sensor states and updates."""
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != expected_updated_state

    new_vehicle_status = deepcopy(vehicle_status)
    update_status_value_fn(new_vehicle_status)
    client.get_vehicle_status.return_value = new_vehicle_status
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    updated_state = hass.states.get(entity_id)
    assert updated_state
    assert updated_state.state == expected_updated_state


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.peugeot_suv_3008_fuel_total_consumption",
        "sensor.peugeot_suv_3008_battery_total_capacity",
        "sensor.peugeot_suv_3008_residual_electric_energy",
        "sensor.peugeot_suv_3008_battery_capacity",
        "sensor.peugeot_suv_3008_battery_resistance",
        "sensor.peugeot_suv_3008_charging_status",
        "sensor.peugeot_suv_3008_charging_remaining_time",
        "sensor.peugeot_suv_3008_charging_speed",
        "sensor.peugeot_suv_3008_charging_mode",
        "sensor.peugeot_suv_3008_next_charge",
        "sensor.peugeot_suv_3008_thermic_engine_coolant_level",
        "sensor.peugeot_suv_3008_thermic_engine_coolant_temperature",
        "sensor.peugeot_suv_3008_thermic_engine_oil_level",
        "sensor.peugeot_suv_3008_thermic_engine_oil_temperature",
        "sensor.peugeot_suv_3008_thermic_engine_air_temperature",
        "sensor.peugeot_suv_3008_ignition",
        "sensor.peugeot_suv_3008_powertrain_status",
        "sensor.peugeot_suv_3008_privacy",
        "sensor.peugeot_suv_3008_auxiliary_battery_health",
        "sensor.peugeot_suv_3008_auto_e_call_triggering",
        "sensor.peugeot_suv_3008_mileage",
        "sensor.peugeot_suv_3008_acceleration",
        "sensor.peugeot_suv_3008_speed",
        "sensor.peugeot_suv_3008_environment_air_temperature",
        "sensor.peugeot_suv_3008_driving_mode",
        "sensor.peugeot_suv_3008_preconditioning_status",
        "sensor.peugeot_suv_3008_fuel_energy_level",
        "sensor.peugeot_suv_3008_fuel_instant_consumption",
        "sensor.peugeot_suv_3008_thermic_engine_speed",
        "sensor.peugeot_suv_3008_preconditioning_program_1",
    ],
)
async def test_unavailability_on_api_error(
    hass: HomeAssistant, client: MagicMock, entity_id: str
) -> None:
    """Tests that the sensors become unavailable on API error."""
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != STATE_UNAVAILABLE

    client.get_vehicle_status.return_value = None
    client.get_vehicle_status.side_effect = StellantisError
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    updated_state = hass.states.get(entity_id)
    assert updated_state
    assert updated_state.state == STATE_UNAVAILABLE
