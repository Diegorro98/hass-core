"""Test Stellantis binary sensor platform."""

from collections.abc import Callable
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from stellantis.model import (
    BeltStatusEnum,
    LightStatus,
    OnboardCapabilitiesEnum,
    Status,
)
from stellantis.model.error import StellantisError

from homeassistant.components.stellantis.const import UPDATE_INTERVAL
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

SCOPE_RELATED_ENTITIES = {
    OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_ENERGIES: {
        "binary_sensor.peugeot_suv_3008_plugged",
    },
    OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_SAFETY: {
        "binary_sensor.peugeot_suv_3008_driver_belt_status",
    },
    OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_KINETIC: {
        "binary_sensor.peugeot_suv_3008_moving",
    },
    OnboardCapabilitiesEnum.DATA_TELEMETRY_ENVIRONMENT: {
        "binary_sensor.peugeot_suv_3008_environment_light",
    },
    OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_LIGHTING_SYSTEM: {
        "binary_sensor.peugeot_suv_3008_front_left_turn_light",
    },
    OnboardCapabilitiesEnum.DATA_TELEMETRY_VEHICLE_DOORS_STATE: {
        "binary_sensor.peugeot_suv_3008_driver_door",
    },
}


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
    assert not hass.states.is_state(entity_id, expected_updated_state)

    new_vehicle_status = deepcopy(vehicle_status)
    update_status_value_fn(new_vehicle_status)
    client.get_vehicle_status.return_value = new_vehicle_status
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, expected_updated_state)


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
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    updated_state = hass.states.get(entity_id)
    assert updated_state
    assert updated_state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_ids", "onboard_capabilities_data"),
    [(entity_ids, [scope]) for scope, entity_ids in SCOPE_RELATED_ENTITIES.items()],
    indirect=["onboard_capabilities_data"],
)
async def test_entity_provided_if_entity_scope_present(
    hass: HomeAssistant,
    entity_ids: set[str],
) -> None:
    """Test that entities are created if their scope is present in vehicle details."""
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) is not None, f"Entity {entity_id} not found"


@pytest.mark.parametrize(
    ("entity_ids", "onboard_capabilities_data"),
    [
        (entity_ids, list(set(OnboardCapabilitiesEnum.__members__.values()) - {scope}))
        for scope, entity_ids in SCOPE_RELATED_ENTITIES.items()
    ],
    indirect=["onboard_capabilities_data"],
)
async def test_entity_not_provided_if_entity_scope_not_present(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> None:
    """Test that entities are not created if their scope is not present in vehicle details."""
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) is None, f"Entity {entity_id} found"


@pytest.mark.parametrize("onboard_capabilities_data", [None], indirect=True)
@pytest.mark.parametrize(
    "entity_id",
    [
        entity_id
        for entity_ids in SCOPE_RELATED_ENTITIES.values()
        for entity_id in entity_ids
    ],
)
async def test_entity_provided_but_disabled_if_not_onboarding_capabilities_data(
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> None:
    """Test that entities are not created if their scope is not present in vehicle details."""
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
