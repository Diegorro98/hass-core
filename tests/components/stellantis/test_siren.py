"""Test for Stellantis siren platform."""

from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import Vehicle
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SIREN]


@pytest.mark.usefixtures("send_webhook_result_success")
async def test_remote_action_callback_successful(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the result of a successful remote action callback."""
    entity_id = "siren.peugeot_suv_3008_horn"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        Platform.SIREN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON


@pytest.mark.usefixtures("send_webhook_result_failed")
async def test_remote_action_callback_failed_result(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    entity_id = "siren.peugeot_suv_3008_horn"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SIREN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


async def test_remote_action_callback_failed_executing(
    hass: HomeAssistant,
    client: MagicMock,
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl.side_effect = StellantisError("Test error")

    entity_id = "siren.peugeot_suv_3008_horn"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SIREN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


async def test_remote_action_callback_timeout(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""
    entity_id = "siren.peugeot_suv_3008_horn"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        side_effect=TimeoutError(),
    ):
        await hass.services.async_call(
            Platform.SIREN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


@pytest.mark.usefixtures("send_webhook_result_success")
@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.parametrize("entity_id", ["siren.peugeot_suv_3008_horn"])
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
        Platform.SIREN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )
