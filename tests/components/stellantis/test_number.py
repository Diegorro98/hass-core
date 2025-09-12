"""Test for Stellantis number platform."""

from collections.abc import Callable
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stellantis.model import ChargingPowerLevel, RemotePostResponse, Status, Vehicle
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.stellantis.const import UPDATE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import RESULT_EXCEPTION, RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.NUMBER]


@pytest.mark.parametrize(
    ("expected_updated_state", "update_status_value_fn"),
    [
        (
            "5.0",
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "charging_power_level",
                ChargingPowerLevel.LEVEL5,
            ),
        ),
        (
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "charging_power_level",
                None,
            ),
        ),
        (
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric, "charging", None
            ),
        ),
    ],
)
async def test_lock_states_and_updates(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_status: Status,
    expected_updated_state: str,
    update_status_value_fn: Callable[[Status], None],
) -> None:
    """Test Stellantis lock states and updates."""
    entity_id = "number.peugeot_suv_3008_charging_power_level"
    initial_state = hass.states.get(entity_id)
    assert initial_state

    new_vehicle_status = deepcopy(vehicle_status)
    update_status_value_fn(new_vehicle_status)
    client.get_vehicle_status.return_value = new_vehicle_status
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, expected_updated_state)


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
    entity_id = "number.peugeot_suv_3008_charging_power_level"
    state = hass.states.get(entity_id)
    assert state
    objective = 2.0
    assert state.state != str(objective)

    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: objective},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == str(objective)


@pytest.mark.parametrize(
    ("send_webhook_result"),
    [[RESULT_FAILED], [RESULT_PENDING, RESULT_FAILED]],
    indirect=True,
)
async def test_remote_action_callback_failed_result(
    hass: HomeAssistant, send_webhook_result: None
) -> None:
    """Test the result of a failed remote action callback."""
    entity_id = "number.peugeot_suv_3008_charging_power_level"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError, match=r"Remote action.*failed"):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 2.0},
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

    entity_id = "number.peugeot_suv_3008_charging_power_level"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError, match=r"Execution.*remote action.*failed"):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 2.0},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


async def test_remote_action_missing_callback_id(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    entity_id = "number.peugeot_suv_3008_charging_power_level"
    config_entry.runtime_data.callback_id = None

    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError, match=r"Callback.*not found"):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 2.0},
            blocking=True,
        )

    client.send_remote_to_vhl.assert_not_awaited()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


async def test_remote_action_missing_remote_action_id(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl = AsyncMock(return_value=RemotePostResponse())
    entity_id = "number.peugeot_suv_3008_charging_power_level"

    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 2.0},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


async def test_remote_action_callback_timeout(hass: HomeAssistant) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""
    entity_id = "number.peugeot_suv_3008_charging_power_level"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        side_effect=TimeoutError(),
    ):
        await hass.services.async_call(
            Platform.NUMBER,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 2.0},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == old_state


@pytest.mark.usefixtures("send_webhook_result")
@pytest.mark.parametrize("entity_id", ["number.peugeot_suv_3008_charging_power_level"])
async def test_remote_action_payload(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_details: Vehicle,
    entity_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the result of a successful remote action callback."""
    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 2.0},
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )


@pytest.mark.parametrize(
    "vehicle_details_mod_fn",
    [
        lambda vehicle_details: setattr(
            vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.preferences,
            "level",
            False,
        ),
        lambda vehicle_details: setattr(
            vehicle_details.embedded.extension.onboard_capabilities.remote.charging,
            "supported",
            False,
        ),
    ],
    indirect=True,
)
async def test_no_actionable_entity_if_not_supported(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that no charging_level entity is created for a vehicle that does not support it."""
    assert not entity_registry.async_get("number.peugeot_suv_3008_charging_power_level")


@pytest.mark.parametrize(
    "vehicle_details_mod_fn",
    [
        lambda vehicle_details: setattr(
            vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.preferences,
            "level",
            None,
        ),
        lambda vehicle_details: setattr(
            vehicle_details.embedded.extension, "onboard_capabilities", None
        ),
    ],
    indirect=True,
)
async def test_actionable_entity_unknown_supported_disabled(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that no charging_level entity is created but it is disabled if the support is unknown."""
    entity = entity_registry.async_get("number.peugeot_suv_3008_charging_power_level")
    assert entity
    assert entity.disabled
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
