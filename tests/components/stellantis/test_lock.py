"""Test for Stellantis lock platform."""

from unittest.mock import patch

from homeassistant.components.lock import LockState
from homeassistant.components.stellantis.api import VehicleDetails
from homeassistant.components.stellantis.const import ATTR_REMOTE_ACTION_ID
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import RESULT_FAILED, RESULT_SUCCESS
from .helpers import create_future_result

from tests.common import MockConfigEntry


async def test_remote_action_callback_successful(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: VehicleDetails,
) -> None:
    """Test the result of a successful remote action callback."""
    await hass.async_block_till_done()
    assert config_entry
    test_remote_action_id = "test_remote_action_id"
    entity_id = entity_registry.async_get_entity_id(
        Platform.LOCK,
        config_entry.domain,
        f"{vehicle_details.vin}-doors",
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == LockState.UNLOCKED

    with (
        patch(
            "homeassistant.components.stellantis.api.StellantisApi.async_send_remote_action",
            return_value={ATTR_REMOTE_ACTION_ID: test_remote_action_id},
        ),
        patch(
            "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
            return_value=create_future_result(RESULT_SUCCESS),
        ) as await_future_mock,
    ):
        await hass.services.async_call(
            Platform.LOCK,
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: entity_id,
            },
        )
        await hass.async_block_till_done()

    await_future_mock.assert_called_once()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == LockState.LOCKED


async def test_remote_action_callback_failed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: VehicleDetails,
) -> None:
    """Test the result of a failed remote action callback."""
    await hass.async_block_till_done()
    assert config_entry
    test_remote_action_id = "test_remote_action_id"
    entity_id = entity_registry.async_get_entity_id(
        Platform.LOCK,
        config_entry.domain,
        f"{vehicle_details.vin}-doors",
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with (
        patch(
            "homeassistant.components.stellantis.api.StellantisApi.async_send_remote_action",
            return_value={ATTR_REMOTE_ACTION_ID: test_remote_action_id},
        ),
        patch(
            "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
            return_value=create_future_result(RESULT_FAILED),
        ) as await_future_mock,
        patch(
            "homeassistant.exceptions.HomeAssistantError.__init__", return_value=None
        ) as mock_home_assistant_error,
    ):
        await hass.services.async_call(
            Platform.LOCK,
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: entity_id,
            },
        )
        await hass.async_block_till_done()

    await_future_mock.assert_called_once()
    mock_home_assistant_error.assert_called_once()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state
