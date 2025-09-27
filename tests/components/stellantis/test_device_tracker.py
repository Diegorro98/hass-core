"""Tests for Stellantis device tracker platform."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from stellantis.model import FixStatus, LocationType, OnboardCapabilitiesEnum, Status
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker.config_entry import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
)
from homeassistant.components.stellantis.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.DEVICE_TRACKER]


async def test_device_tracker_state(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test the device tracker state."""
    state = hass.states.get("device_tracker.peugeot_suv_3008")
    assert state
    assert snapshot == state.attributes


async def test_device_tracker_updates(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    client: MagicMock,
    vehicle_status: Status,
) -> None:
    """Test that the device tracker updates its state."""
    entity_id = "device_tracker.peugeot_suv_3008"
    initial_state = hass.states.get(entity_id)
    assert initial_state

    new_vehicle_status = deepcopy(vehicle_status)
    assert new_vehicle_status.last_position

    new_vehicle_status.last_position.geometry.coordinates = [0.0, 0.0, 100.0]
    new_vehicle_status.last_position.properties.created_at = datetime(2025, 1, 1)
    new_vehicle_status.last_position.properties.fix_status = FixStatus.THREE_D
    new_vehicle_status.last_position.properties.heading = 180
    new_vehicle_status.last_position.properties.signal_quality = 1
    new_vehicle_status.last_position.properties.type = LocationType.ACQUIRE

    client.get_vehicle_status.return_value = new_vehicle_status
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state

    for attr in (
        ATTR_LATITUDE,
        ATTR_LONGITUDE,
        "altitude",
        "heading",
        "signal_quality",
        "type",
        "created_at",
    ):
        assert state.attributes.get(attr) != initial_state.attributes.get(attr)
    assert snapshot == state.attributes


async def test_unavailability_on_api_error(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Tests that the device tracker becomes unavailable on API error."""
    entity_id = "device_tracker.peugeot_suv_3008"
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


async def test_device_tracker_availability_position_none(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_status: Status,
) -> None:
    """Test the availability of the entity when the position is None."""
    entity_id = "device_tracker.peugeot_suv_3008"
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != STATE_UNAVAILABLE

    new_vehicle_status = deepcopy(vehicle_status)
    assert new_vehicle_status.last_position
    new_vehicle_status.last_position = None

    client.get_vehicle_status.return_value = new_vehicle_status
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_device_tracker_availability_update_failed(
    hass: HomeAssistant,
    client: MagicMock,
) -> None:
    """Test the availability of the entity when the position is None."""
    entity_id = "device_tracker.peugeot_suv_3008"
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != STATE_UNAVAILABLE

    client.get_vehicle_status = AsyncMock(side_effect=StellantisError())
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "onboard_capabilities_data",
    [[OnboardCapabilitiesEnum.DATA_POSITION]],
    indirect=True,
)
async def test_entity_provided_if_entity_scope_present(
    hass: HomeAssistant,
) -> None:
    """Test that entities are created if their scope is present in vehicle details."""
    assert hass.states.get("device_tracker.peugeot_suv_3008") is not None, (
        "Entity not found"
    )


@pytest.mark.parametrize(
    "onboard_capabilities_data",
    [
        list(
            set(OnboardCapabilitiesEnum.__members__.values())
            - {OnboardCapabilitiesEnum.DATA_POSITION}
        )
    ],
    indirect=True,
)
async def test_entity_not_provided_if_entity_scope_not_present(
    hass: HomeAssistant,
) -> None:
    """Test that entities are not created if their scope is not present in vehicle details."""
    assert hass.states.get("device_tracker.peugeot_suv_3008") is None, "Entity found"


@pytest.mark.parametrize("onboard_capabilities_data", [None], indirect=True)
async def test_entity_provided_but_disabled_if_not_onboarding_capabilities_data(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that entities are not created if their scope is not present in vehicle details."""
    entity = entity_registry.async_get("device_tracker.peugeot_suv_3008")
    assert entity
    assert entity.disabled
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
