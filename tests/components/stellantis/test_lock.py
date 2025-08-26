"""Test for Stellantis lock platform."""

from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import RemotePostResponse, Vehicle

from homeassistant.components.lock import LockState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_UNLOCK, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import RESULT_FAILED, RESULT_SUCCESS
from .helpers import create_future_result

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.LOCK]


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
        Platform.LOCK,
        config_entry.domain,
        f"{vehicle_details.vin}-doors",
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == LockState.LOCKED

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        return_value=create_future_result(RESULT_SUCCESS),
    ) as await_future_mock:
        await hass.services.async_call(
            Platform.LOCK,
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    await_future_mock.assert_called_once()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == LockState.UNLOCKED


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
        Platform.LOCK,
        config_entry.domain,
        f"{vehicle_details.vin}-doors",
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
            Platform.LOCK,
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state
