"""Test for Stellantis light platform."""

from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import IgnitionType, Status, Vehicle
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
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
from homeassistant.setup import async_setup_component

from .const import RESULT_EXCEPTION, RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.LIGHT]


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
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

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

    with pytest.raises(HomeAssistantError):
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

    with pytest.raises(HomeAssistantError):
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
