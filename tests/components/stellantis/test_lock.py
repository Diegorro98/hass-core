"""Test for Stellantis lock platform."""

from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import RemotePostResponse, Vehicle
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import LockState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.LOCK]


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("send_webhook_result_success")
async def test_remote_action_callback_successful(
    hass: HomeAssistant,
    client: MagicMock,
) -> None:
    """Test the result of a successful remote action callback."""
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    entity_id = "lock.peugeot_suv_3008_doors"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == LockState.LOCKED

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
    assert state.state == LockState.UNLOCKED


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("send_webhook_result_failed")
async def test_remote_action_callback_failed_result(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    entity_id = "lock.peugeot_suv_3008_doors"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError):
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


@pytest.mark.usefixtures("setup_integration")
async def test_remote_action_callback_failed_executing(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl.side_effect = StellantisError("Test error")

    entity_id = "lock.peugeot_suv_3008_doors"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError):
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


@pytest.mark.usefixtures("setup_integration")
async def test_remote_action_callback_timeout(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    entity_id = "lock.peugeot_suv_3008_doors"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        side_effect=TimeoutError(),
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


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("send_webhook_result_success")
@pytest.mark.parametrize("service", [SERVICE_LOCK, SERVICE_UNLOCK])
@pytest.mark.parametrize("entity_id", ["lock.peugeot_suv_3008_doors"])
async def test_remote_action_payload(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_details: Vehicle,
    entity_id: str,
    service: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the result of a successful remote action callback."""
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    await hass.services.async_call(
        Platform.LOCK,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )
