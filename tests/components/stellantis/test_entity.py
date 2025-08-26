"""Test for Stellantis entity base classes."""

from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import RemotePostResponse, Vehicle

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS
from .helpers import create_future_result

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.mark.usefixtures("setup_integration")
async def test_remote_action_callback_successful(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test the result of a successful remote action callback."""
    test_remote_action_id = "test_remote_action_id"
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id=test_remote_action_id
    )

    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning",
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        return_value=create_future_result(RESULT_SUCCESS),
    ) as await_future_mock:
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    await_future_mock.assert_called_once()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_integration")
async def test_remote_action_callback_failed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test the result of a failed remote action callback."""
    test_remote_action_id = "test_remote_action_id"
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id=test_remote_action_id
    )

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
        pytest.raises(HomeAssistantError),
        patch(
            "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
            return_value=create_future_result(RESULT_FAILED),
        ),
    ):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


@pytest.mark.usefixtures("setup_integration")
async def test_remote_action_callback_pending_and_done(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test the result of a pending remote action callback."""
    test_remote_action_id = "test_remote_action_id"
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id=test_remote_action_id
    )

    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning",
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        side_effect=[
            create_future_result(result) for result in (RESULT_PENDING, RESULT_SUCCESS)
        ],
    ) as await_future_mock:
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    assert await_future_mock.call_count == 2
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


@pytest.mark.usefixtures("setup_integration")
async def test_remote_action_callback_timeout(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""
    test_remote_action_id = "test_remote_action_id"
    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH,
        config_entry.domain,
        f"{vehicle_details.vin}-preconditioning",
    )
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id=test_remote_action_id
    )

    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        side_effect=TimeoutError(),
    ):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state
