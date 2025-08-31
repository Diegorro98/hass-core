"""Test Stellantis binary sensor platform."""

from collections.abc import Callable
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from stellantis.model import BeltStatusEnum, LightStatus, Status
from stellantis.model.error import StellantisError

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.parametrize(
    ("entity_id", "expected_updated_state", "update_status_value_fn"),
    [
        (
            "binary_sensor.peugeot_suv_3008_plugged",
            STATE_OFF,
            lambda status: setattr(
                status.energies[1].extension.electric.charging, "plugged", False
            ),
        ),
        (
            "binary_sensor.peugeot_suv_3008_plugged",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging, "plugged", None
            ),
        ),
        (
            "binary_sensor.peugeot_suv_3008_plugged",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric, "charging", None
            ),
        ),
        (
            "binary_sensor.peugeot_suv_3008_driver_belt_status",
            STATE_OFF,
            lambda status: setattr(
                status.safety.belt_status[0], "belt", BeltStatusEnum.OMISSION
            ),
        ),
        (
            "binary_sensor.peugeot_suv_3008_driver_belt_status",
            STATE_UNKNOWN,
            lambda status: setattr(status.safety.belt_status[0], "belt", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_driver_belt_status",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.safety, "belt_status", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_moving",
            STATE_OFF,
            lambda status: setattr(status.kinetic, "moving", False),
        ),
        (
            "binary_sensor.peugeot_suv_3008_moving",
            STATE_UNKNOWN,
            lambda status: setattr(status.kinetic, "moving", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_moving",
            STATE_UNAVAILABLE,
            lambda status: setattr(status, "kinetic", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_environment_light",
            STATE_OFF,
            lambda status: setattr(status.environment.luminosity, "day", False),
        ),
        (
            "binary_sensor.peugeot_suv_3008_environment_light",
            STATE_UNKNOWN,
            lambda status: setattr(status.environment.luminosity, "day", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_environment_light",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.environment, "luminosity", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_front_left_turn_light",
            STATE_ON,
            lambda status: setattr(
                status.lighting_system.turn[0], "status", LightStatus.ON
            ),
        ),
        (
            "binary_sensor.peugeot_suv_3008_front_left_turn_light",
            STATE_UNKNOWN,
            lambda status: setattr(status.lighting_system.turn[0], "status", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_front_left_turn_light",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.lighting_system, "turn", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_driver_door",
            STATE_OFF,
            lambda status: setattr(status.doors_state.opening[0], "state", "Closed"),
        ),
        (
            "binary_sensor.peugeot_suv_3008_driver_door",
            STATE_UNKNOWN,
            lambda status: setattr(status.doors_state.opening[0], "state", None),
        ),
        (
            "binary_sensor.peugeot_suv_3008_driver_door",
            STATE_UNAVAILABLE,
            lambda status: setattr(status.doors_state, "opening", None),
        ),
    ],
)
async def test_binary_sensor_state_and_updates(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_status: Status,
    entity_id: str,
    expected_updated_state: str,
    update_status_value_fn: Callable[[Status], None],
) -> None:
    """Test Stellantis binary sensor states and updates."""
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
        "binary_sensor.peugeot_suv_3008_plugged",
        "binary_sensor.peugeot_suv_3008_driver_belt_status",
        "binary_sensor.peugeot_suv_3008_moving",
        "binary_sensor.peugeot_suv_3008_environment_light",
        "binary_sensor.peugeot_suv_3008_front_left_turn_light",
        "binary_sensor.peugeot_suv_3008_driver_door",
    ],
)
async def test_unavailability_on_api_error(
    hass: HomeAssistant, client: MagicMock, entity_id: str
) -> None:
    """Tests that the binary sensors become unavailable on API error."""
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
