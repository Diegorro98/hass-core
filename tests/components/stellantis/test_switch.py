"""Test for Stellantis switch platform."""

from collections.abc import Callable
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stellantis.model import (
    AirConditioningStatus,
    ChargeScheduleProgram,
    ChargingStatusEnum,
    ChargingType,
    DoorLockedState,
    IgnitionType,
    Motorization,
    RemotePostResponse,
    Status,
    Vehicle,
)
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stellantis.const import UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import RESULT_EXCEPTION, RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.mark.parametrize(
    ("entity_id", "expected_updated_state", "update_status_value_fn"),
    [
        (
            "switch.peugeot_suv_3008_preconditioning",
            STATE_ON,
            lambda status: setattr(
                status.preconditioning.air_conditioning,
                "status",
                AirConditioningStatus.ENABLED,
            ),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning",
            STATE_OFF,
            lambda status: setattr(
                status.preconditioning.air_conditioning,
                "status",
                AirConditioningStatus.DISABLED,
            ),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning",
            STATE_UNKNOWN,
            lambda status: setattr(status.preconditioning, "air_conditioning", None),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning_program_1",
            STATE_OFF,
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[0], "enabled", False
            ),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning_program_1",
            STATE_ON,
            lambda status: setattr(
                status.preconditioning.air_conditioning.programs[0], "enabled", True
            ),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning_program_1",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.preconditioning.air_conditioning, "programs", None
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            STATE_ON,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.IN_PROGRESS,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            STATE_OFF,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.STOPPED,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.DISCONNECTED,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.FAILURE,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.FINISHED,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric,
                "charging",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            STATE_ON,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "type",
                ChargingType.PARTIAL,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            STATE_OFF,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "type",
                ChargingType.FULL,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "type",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.DISCONNECTED,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.FAILURE,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "status",
                ChargingStatusEnum.FINISHED,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric,
                "charging",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            STATE_OFF,
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule.programs[0],
                "enabled",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            STATE_ON,
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule.programs[0],
                "enabled",
                True,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule.programs[0],
                "enabled",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            STATE_OFF,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "schedule",
                [ChargeScheduleProgram(enabled=False, start="PT0S")],
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            STATE_ON,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "schedule",
                [ChargeScheduleProgram(enabled=True, start="PT0S")],
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "schedule",
                [ChargeScheduleProgram(enabled=None, start="PT0S")],
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "schedule",
                [],
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging,
                "schedule",
                None,
            ),
        ),
    ],
)
async def test_switch_state_and_updates(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_status: Status,
    entity_id: str,
    expected_updated_state: str,
    update_status_value_fn: Callable[[Status], None],
) -> None:
    """Test Stellantis switch states and updates."""
    new_vehicle_status = deepcopy(vehicle_status)
    update_status_value_fn(new_vehicle_status)
    client.get_vehicle_status.return_value = new_vehicle_status
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, expected_updated_state)


@pytest.mark.parametrize(
    ("motorization", "ignition", "locked_states", "battery_level", "available"),
    [
        (Motorization.HYBRID, IgnitionType.STOP, [DoorLockedState.LOCKED], 20, True),
        (Motorization.HYBRID, IgnitionType.STOP, [DoorLockedState.LOCKED], 19, False),
        (Motorization.ELECTRIC, IgnitionType.STOP, [DoorLockedState.LOCKED], 50, True),
        (Motorization.ELECTRIC, IgnitionType.STOP, [DoorLockedState.LOCKED], 49, False),
        (Motorization.THERMIC, IgnitionType.STOP, [DoorLockedState.LOCKED], 100, False),
        (Motorization.HYBRID, IgnitionType.START, [DoorLockedState.LOCKED], 100, False),
        (
            Motorization.HYBRID,
            IgnitionType.START_UP,
            [DoorLockedState.LOCKED],
            100,
            False,
        ),
        (
            Motorization.HYBRID,
            IgnitionType.STOP,
            [DoorLockedState.SUPER_LOCKED],
            100,
            True,
        ),
        (
            Motorization.HYBRID,
            IgnitionType.STOP,
            [DoorLockedState.UNLOCKED],
            100,
            False,
        ),
        (Motorization.HYBRID, IgnitionType.STOP, [], 100, True),
        (None, IgnitionType.STOP, [DoorLockedState.LOCKED], 100, True),
        (Motorization.HYBRID, None, [DoorLockedState.LOCKED], 100, True),
        (Motorization.HYBRID, IgnitionType.STOP, None, 100, True),
        (Motorization.HYBRID, IgnitionType.STOP, [DoorLockedState.LOCKED], None, True),
    ],
)
async def test_preconditioning_switch_unavailability_conditions(
    hass: HomeAssistant,
    client: MagicMock,
    vehicle_details: Vehicle,
    vehicle_status: Status,
    motorization: Motorization | None,
    ignition: IgnitionType | None,
    locked_states: list[DoorLockedState] | None,
    battery_level: int | None,
    available: bool,
) -> None:
    """Tests the unavailability conditions for the preconditioning switch."""
    entity_id = "switch.peugeot_suv_3008_preconditioning"
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != STATE_UNAVAILABLE

    vehicle_details.motorization = motorization
    new_vehicle_status = deepcopy(vehicle_status)
    if ignition is not None:
        new_vehicle_status.ignition.type = ignition
    else:
        new_vehicle_status.ignition = None
    new_vehicle_status.doors_state.locked_states = locked_states
    new_vehicle_status.energies[1].level = battery_level
    client.get_vehicle_status.return_value = new_vehicle_status

    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    updated_state = hass.states.get(entity_id)
    assert updated_state
    if available:
        assert updated_state.state != STATE_UNAVAILABLE
    else:
        assert updated_state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "entity_id",
    [
        "switch.peugeot_suv_3008_preconditioning",
        "switch.peugeot_suv_3008_preconditioning_program_1",
        "switch.peugeot_suv_3008_charge",
        "switch.peugeot_suv_3008_partial_charge",
    ],
)
async def test_availability_on_api_error(
    hass: HomeAssistant, client: MagicMock, entity_id: str
) -> None:
    """Tests that the switches does not become unavailable on API error."""
    initial_state = hass.states.get(entity_id)
    assert initial_state
    assert initial_state.state != STATE_UNAVAILABLE

    client.get_vehicle_status.return_value = None
    client.get_vehicle_status.side_effect = StellantisError
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

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
    entity_id = "switch.peugeot_suv_3008_preconditioning"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

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
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("send_webhook_result"),
    [[RESULT_FAILED], [RESULT_PENDING, RESULT_FAILED]],
    indirect=True,
)
async def test_remote_action_callback_failed_result(
    hass: HomeAssistant, send_webhook_result: None
) -> None:
    """Test the result of a failed remote action callback."""
    entity_id = "switch.peugeot_suv_3008_preconditioning"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError, match=r"Remote action.*failed"):
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


async def test_remote_action_callback_failed_executing(
    hass: HomeAssistant, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    client.send_remote_to_vhl.side_effect = StellantisError("Test error")

    entity_id = "switch.peugeot_suv_3008_preconditioning"
    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError, match=r"Execution.*remote action.*failed"):
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


async def test_remote_action_missing_callback_id(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """Test the result of a failed remote action callback."""
    entity_id = "switch.peugeot_suv_3008_preconditioning"
    config_entry.runtime_data.callback_id = None

    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

    with pytest.raises(HomeAssistantError, match=r"Callback.*not found"):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: entity_id,
            },
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
    entity_id = "switch.peugeot_suv_3008_preconditioning"

    state = hass.states.get(entity_id)
    assert state
    old_state = state.state

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


async def test_remote_action_callback_timeout(hass: HomeAssistant) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""
    entity_id = "switch.peugeot_suv_3008_preconditioning"
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


@pytest.mark.usefixtures("send_webhook_result")
@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.parametrize(
    "entity_id",
    [
        "switch.peugeot_suv_3008_preconditioning",
        "switch.peugeot_suv_3008_charge",
        "switch.peugeot_suv_3008_partial_charge",
        "switch.peugeot_suv_3008_preconditioning_program_1",
        "switch.peugeot_suv_3008_charging_program_1",
    ],
)
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
        Platform.SWITCH,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )


@pytest.mark.parametrize(
    ("entity_id", "vehicle_details_mod_fn"),
    [
        (
            "switch.peugeot_suv_3008_preconditioning",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning,
                "supported",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters,
                "immediate",
                False,
            ),
        ),
        (
            "switch,peugeot_suv_3008_preconditioning_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning,
                "supported",
                False,
            ),
        ),
        (
            "switch,peugeot_suv_3008_preconditioning_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters.programs,
                "size",
                0,
            ),
        ),
        (
            "switch,peugeot_suv_3008_preconditioning_program_4",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters.programs,
                "size",
                2,
            ),
        ),
        (
            "switch,peugeot_suv_3008_preconditioning_program_5",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters.programs,
                "size",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging,
                "supported",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            lambda vehicle_details: (
                setattr(
                    vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.immediate,
                    "start",
                    False,
                ),
                setattr(
                    vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.immediate,
                    "stop",
                    False,
                ),
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging,
                "supported",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.preferences,
                "type",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging,
                "supported",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "supported",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "size",
                0,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_4",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "size",
                2,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_5",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "size",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1_charge_until_full",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging,
                "supported",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1_charge_until_full",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "supported",
                False,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1_charge_until_full",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "size",
                0,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_4_charge_until_full",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "size",
                2,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_5_charge_until_full",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "size",
                None,
            ),
        ),
    ],
    indirect=["vehicle_details_mod_fn"],
)
async def test_no_actionable_entity_if_not_supported(
    entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test that no actionable switch entities are created for a vehicle that does not support it."""
    assert not entity_registry.async_get(entity_id)


@pytest.mark.parametrize(
    ("entity_id", "vehicle_details_mod_fn"),
    [
        (
            "switch.peugeot_suv_3008_preconditioning",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters,
                "immediate",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension, "onboard_capabilities", None
            ),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters.programs,
                "size",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_preconditioning_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension, "onboard_capabilities", None
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters,
                "immediate",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charge",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension,
                "onboard_capabilities",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.preferences,
                "type",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_partial_charge",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension,
                "onboard_capabilities",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters,
                "schedule",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                "size",
                None,
            ),
        ),
        (
            "switch.peugeot_suv_3008_charging_program_1",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension, "onboard_capabilities", None
            ),
        ),
    ],
    indirect=["vehicle_details_mod_fn"],
)
async def test_actionable_entity_unknown_supported_disabled(
    entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test that actionable switch entities are created but it is disabled if the support is unknown."""
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
