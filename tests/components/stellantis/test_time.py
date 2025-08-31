"""Test for Stellantis time platform."""

from collections.abc import Callable
from copy import deepcopy
from datetime import time
from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import Status, Vehicle
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.time import ATTR_TIME, SERVICE_SET_VALUE
from homeassistant.const import (
    ATTR_ENTITY_ID,
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
    return [Platform.TIME]


@pytest.mark.parametrize(
    ("entity_id", "expected_updated_state", "update_status_value_fn"),
    [
        (
            "time.peugeot_suv_3008_charging_time",
            "22:00:00",
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "next_delayed_time",
                "PT22H",
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_time",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "next_delayed_time",
                None,
            ),
        ),
        (
            "time.peugeot_suv_3008_preconditioning_program_1_start_time",
            "22:00:00",
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[0], "start", "PT22H"
            ),
        ),
        (
            "time.peugeot_suv_3008_preconditioning_program_1_start_time",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[0],
                "start",
                "BAD_FORMAT",
            ),
        ),
        (
            "time.peugeot_suv_3008_preconditioning_program_1_start_time",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.preconditioning.air_conditioning, "programs", None
            ),
        ),
    ],
)
async def test_time_state_and_updates(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_status: Status,
    entity_id: str,
    expected_updated_state: str,
    update_status_value_fn: Callable[[Status], None],
) -> None:
    """Test Stellantis time states and updates."""
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != expected_updated_state

    new_vehicle_status = deepcopy(vehicle_status)
    update_status_value_fn(new_vehicle_status)
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
    assert updated_state.state == expected_updated_state


@pytest.mark.parametrize(
    "entity_id",
    [
        "time.peugeot_suv_3008_charging_time",
    ],
)
async def test_availability_on_api_error(
    hass: HomeAssistant, client: MagicMock, entity_id: str
) -> None:
    """Tests that the time entities does not become unavailable on API error."""
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


@pytest.mark.parametrize(
    ("send_webhook_result"),
    [[RESULT_FAILED], [RESULT_PENDING, RESULT_FAILED]],
    indirect=True,
)
async def test_remote_action_callback_failed_result(
    hass: HomeAssistant, send_webhook_result: None
) -> None:
    """Test the result of a failed remote action callback."""

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


async def test_remote_action_callback_failed_executing(
    hass: HomeAssistant, client: MagicMock
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


async def test_remote_action_callback_timeout(hass: HomeAssistant) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""

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


@pytest.mark.usefixtures("send_webhook_result")
# These test are repeated to check that the conversion from time object
# to ISO 8601 duration format is working correctly.
@pytest.mark.parametrize("value", [time(22, 0), time(22, 30), time(0, 30), time(0, 0)])
@pytest.mark.parametrize(
    "entity_id",
    [
        "time.peugeot_suv_3008_charging_time",
        "time.peugeot_suv_3008_preconditioning_program_1_start_time",
    ],
)
async def test_remote_action_payload(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_details: Vehicle,
    entity_id: str,
    value: time,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the result of a successful remote action callback."""

    await hass.services.async_call(
        Platform.TIME,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: str(value)},
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )
