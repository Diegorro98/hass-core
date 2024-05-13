"""Test for Stellantis entity base classes."""

from unittest.mock import patch

from homeassistant.components.stellantis.api import VehicleDetails
from homeassistant.components.stellantis.const import ATTR_REMOTE_ACTION_ID
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS
from .helpers import create_future_result

from tests.common import MockConfigEntry


# Test toggle entities
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
        Platform.SWITCH,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning",
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

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
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
        )
        await hass.async_block_till_done()

    await_future_mock.assert_called_once()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


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
        Platform.SWITCH,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning",
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
            Platform.SWITCH,
            SERVICE_TURN_ON,
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


async def test_remote_action_callback_pending_and_done(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: VehicleDetails,
) -> None:
    """Test the result of a pending remote action callback."""
    await hass.async_block_till_done()
    assert config_entry
    test_remote_action_id = "test_remote_action_id"
    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning",
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    with (
        patch(
            "homeassistant.components.stellantis.api.StellantisApi.async_send_remote_action",
            return_value={ATTR_REMOTE_ACTION_ID: test_remote_action_id},
        ),
        patch(
            "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
            side_effect=[
                create_future_result(result)
                for result in (RESULT_PENDING, RESULT_SUCCESS)
            ],
        ) as await_future_mock,
    ):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
        )

        await hass.async_block_till_done()

    await_future_mock.assert_called()
    assert await_future_mock.call_count == 2
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


async def test_remote_action_callback_timeout(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: VehicleDetails,
) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""
    await hass.async_block_till_done()
    assert config_entry
    test_remote_action_id = "test_remote_action_id"
    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning",
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
            side_effect=TimeoutError(),
        ),
    ):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state
