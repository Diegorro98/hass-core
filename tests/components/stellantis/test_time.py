"""Test for Stellantis time platform."""

from datetime import time
from unittest.mock import patch

from homeassistant.components.stellantis.api import VehicleDetails
from homeassistant.components.stellantis.const import ATTR_REMOTE_ACTION_ID
from homeassistant.components.time import ATTR_TIME, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
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
        Platform.TIME,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning_program_1_start_time",
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    objective = str(time(22, 0))
    assert state.state != objective

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
            Platform.TIME,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TIME: objective},
        )
        await hass.async_block_till_done()

    await_future_mock.assert_called_once()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == objective


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
        Platform.TIME,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning_program_1_start_time",
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
            Platform.TIME,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TIME: str(time(22, 0))},
        )
        await hass.async_block_till_done()

    await_future_mock.assert_called_once()
    mock_home_assistant_error.assert_called_once()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state
