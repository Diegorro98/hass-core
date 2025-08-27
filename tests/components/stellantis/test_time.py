"""Test for Stellantis time platform."""

from datetime import time
from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import RemotePostResponse, Vehicle
from stellantis.model.error import StellantisError

from homeassistant.components.time import ATTR_TIME, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.TIME]


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("send_webhook_result_success")
async def test_remote_action_callback_successful(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test the result of a successful remote action callback."""
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    entity_id = "time.peugeot_suv_3008_preconditioning_program_1_start_time"
    state = hass.states.get(entity_id)
    assert state
    objective = str(time(22, 0))
    assert state.state != objective

    await hass.services.async_call(
        Platform.TIME,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: objective},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == objective


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("send_webhook_result_failed")
async def test_remote_action_callback_failed_result(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    entity_id = "time.peugeot_suv_3008_preconditioning_program_1_start_time"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.TIME,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TIME: str(time(22, 0))},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


@pytest.mark.usefixtures("setup_integration")
async def test_remote_action_callback_failed_executing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl.side_effect = StellantisError("Test error")

    entity_id = "time.peugeot_suv_3008_preconditioning_program_1_start_time"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.TIME,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TIME: str(time(22, 0))},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


@pytest.mark.usefixtures("setup_integration")
async def test_remote_action_callback_timeout(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    entity_id = "time.peugeot_suv_3008_preconditioning_program_1_start_time"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        side_effect=TimeoutError(),
    ):
        await hass.services.async_call(
            Platform.TIME,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TIME: str(time(22, 0))},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state
