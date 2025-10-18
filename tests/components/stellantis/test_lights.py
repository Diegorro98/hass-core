"""Test for Stellantis light platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stellantis.model import (
    IgnitionType,
    RemotePostResponse,
    Status,
    Vehicle,
    Vehicles,
    VehiclesEmbedded,
)
from stellantis.model.error import StellantisApiError, StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stellantis.const import (
    DOMAIN,
    UPDATE_INTERVAL,
    VEHICLES_UPDATE_INTERVAL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .const import RESULT_EXCEPTION, RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.LIGHT]


async def test_vehicle_removed_and_added(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test that binary sensors are removed for a removed vehicle and added for a new vehicle."""
    vehicle_vin = vehicle_details.vin
    assert vehicle_vin
    device = device_registry.async_get_device({(DOMAIN, vehicle_vin)})
    assert device

    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    # Simulate vehicle removal
    original_mock = client.get_vehicles_by_device
    client.get_vehicles_by_device = AsyncMock(
        return_value=Vehicles(
            embedded=VehiclesEmbedded(vehicles=[]),
            total=1,
            total_page=1,
            current_page=1,
            links={},
        )
    )
    async_fire_time_changed(hass, dt_util.utcnow() + VEHICLES_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device({(DOMAIN, vehicle_vin)})
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Simulate vehicle addition
    client.get_vehicles_by_device = original_mock
    async_fire_time_changed(hass, dt_util.utcnow() + VEHICLES_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, vehicle_vin)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


async def test_vehicle_removed_and_added_on_vehicle_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test that binary sensors are removed for a removed vehicle and added for a new vehicle."""
    vehicle_vin = vehicle_details.vin
    assert vehicle_vin
    device = device_registry.async_get_device({(DOMAIN, vehicle_vin)})
    assert device

    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    # Simulate vehicle removal
    original_mock = client.get_vehicle_status
    client.get_vehicle_status = AsyncMock(
        side_effect=StellantisApiError(404, "Vehicle not found")
    )
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device({(DOMAIN, vehicle_vin)})
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Simulate vehicle addition
    client.get_vehicle_status = original_mock
    async_fire_time_changed(hass, dt_util.utcnow() + VEHICLES_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert device_registry.async_get_device({(DOMAIN, vehicle_vin)})
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


async def test_unavailability_on_turned_on(
    hass: HomeAssistant, client: MagicMock, vehicle_status: Status
) -> None:
    """Tests that the light becomes unavailable when the car is running."""
    entity_id = "light.peugeot_suv_3008_lights"
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != STATE_UNAVAILABLE

    new_vehicle_status = deepcopy(vehicle_status)
    assert new_vehicle_status.ignition
    new_vehicle_status.ignition.type = IgnitionType.START
    client.get_vehicle_status.return_value = new_vehicle_status
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    updated_state = hass.states.get(entity_id)
    assert updated_state
    assert updated_state.state == STATE_UNAVAILABLE


async def test_availability_on_api_error(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Tests that the light does not become unavailable on API error."""
    entity_id = "light.peugeot_suv_3008_lights"
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != STATE_UNAVAILABLE

    client.get_vehicle_status.return_value = None
    client.get_vehicle_status.side_effect = StellantisError
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    updated_state = hass.states.get(entity_id)
    assert updated_state
    assert updated_state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "send_webhook_result",
    [
        [RESULT_SUCCESS],
        [RESULT_PENDING, RESULT_SUCCESS],
        [RESULT_EXCEPTION, RESULT_SUCCESS],
    ],
    indirect=True,
)
async def test_remote_action_callback_success_result(
    hass: HomeAssistant, send_webhook_result: None
) -> None:
    """Test the result of a successful remote action callback."""

    entity_id = "light.peugeot_suv_3008_lights"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        Platform.LIGHT,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("send_webhook_result"),
    [[RESULT_FAILED], [RESULT_PENDING, RESULT_FAILED]],
    indirect=True,
)
async def test_remote_action_callback_failed_result(
    hass: HomeAssistant, send_webhook_result: None
) -> None:
    """Test the result of a failed remote action callback."""

    entity_id = "light.peugeot_suv_3008_lights"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    with pytest.raises(HomeAssistantError, match=r"Remote action.*failed"):
        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_remote_action_callback_failed_executing(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl.side_effect = StellantisError("Test error")

    entity_id = "light.peugeot_suv_3008_lights"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    with pytest.raises(HomeAssistantError, match=r"Execution.*remote action.*failed"):
        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_remote_action_missing_callback_id(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    entity_id = "light.peugeot_suv_3008_lights"
    config_entry.runtime_data.callback_id = None

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    with pytest.raises(HomeAssistantError, match=r"Callback.*not found"):
        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    client.send_remote_to_vhl.assert_not_awaited()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_remote_action_missing_remote_action_id(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl = AsyncMock(return_value=RemotePostResponse())
    entity_id = "light.peugeot_suv_3008_lights"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        Platform.LIGHT,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_remote_action_callback_timeout(hass: HomeAssistant) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""

    entity_id = "light.peugeot_suv_3008_lights"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        side_effect=TimeoutError(),
    ):
        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


@pytest.mark.usefixtures("send_webhook_result")
@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.parametrize("entity_id", ["light.peugeot_suv_3008_lights"])
async def test_remote_action_payload(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_details: Vehicle,
    entity_id: str,
    service: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the result of a successful remote action callback."""

    await hass.services.async_call(
        Platform.LIGHT,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )


@pytest.mark.parametrize(
    "vehicle_details_mod_fn",
    [
        lambda vehicle_details: setattr(
            vehicle_details.embedded.extension.onboard_capabilities.remote.lights,
            "supported",
            False,
        )
    ],
    indirect=True,
)
async def test_no_actionable_entity_if_not_supported(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that no lights entity is created for a vehicle that does not support it."""
    assert not entity_registry.async_get("light.peugeot_suv_3008_lights")


@pytest.mark.parametrize(
    "vehicle_details_mod_fn",
    [
        lambda vehicle_details: setattr(
            vehicle_details.embedded.extension.onboard_capabilities,
            "remote",
            None,
        ),
        lambda vehicle_details: setattr(
            vehicle_details.embedded.extension, "onboard_capabilities", None
        ),
    ],
    indirect=True,
)
async def test_actionable_entity_unknown_supported_disabled(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that lights entity is created but it is disabled if the support is unknown."""
    entity = entity_registry.async_get("light.peugeot_suv_3008_lights")
    assert entity
    assert entity.disabled
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
