"""Test for Stellantis time platform."""

from collections.abc import Callable
from copy import deepcopy
from datetime import time
from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import Status, Vehicle
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stellantis.const import UPDATE_INTERVAL
from homeassistant.components.time import ATTR_TIME, SERVICE_SET_VALUE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import RESULT_EXCEPTION, RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS

from tests.common import async_fire_time_changed


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
        (
            "time.peugeot_suv_3008_charging_program_1_start_time",
            "22:00:00",
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule.programs[0],
                "start",
                "PT22H",
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_program_1_start_time",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule.programs[0],
                "start",
                "BAD_FORMAT",
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_program_1_start_time",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule,
                "programs",
                None,
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_program_1_end_time",
            "22:00:00",
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule.programs[0],
                "end",
                "PT22H",
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_program_1_end_time",
            STATE_UNKNOWN,
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule.programs[0],
                "end",
                "BAD_FORMAT",
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_program_1_end_time",
            STATE_UNAVAILABLE,
            lambda status: setattr(
                status.energies[1].extension.electric.charging.schedule,
                "programs",
                None,
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
    assert not hass.states.is_state(entity_id, expected_updated_state)

    new_vehicle_status = deepcopy(vehicle_status)
    update_status_value_fn(new_vehicle_status)
    client.get_vehicle_status.return_value = new_vehicle_status
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.is_state(entity_id, expected_updated_state)


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

    with pytest.raises(HomeAssistantError, match=r"Remote action.*failed"):
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

    with pytest.raises(HomeAssistantError, match=r"Execution.*remote action.*failed"):
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
        "time.peugeot_suv_3008_charging_program_1_start_time",
        "time.peugeot_suv_3008_charging_program_1_end_time",
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


@pytest.mark.parametrize(
    ("entity_id", "vehicle_details_mod_fn"),
    [
        (
            "time.peugeot_suv_3008_preconditioning_program_1_start_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning,
                "supported",
                False,
            ),
        ),
        (
            "time.peugeot_suv_3008_preconditioning_program_1_start_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters.programs,
                "size",
                0,
            ),
        ),
        (
            "time.peugeot_suv_3008_preconditioning_program_4_start_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters.programs,
                "size",
                2,
            ),
        ),
        (
            "time.peugeot_suv_3008_preconditioning_program_5_start_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters.programs,
                "size",
                None,
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging,
                "supported",
                False,
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule,
                "next_delayed_time",
                False,
            ),
        ),
        *[
            test
            for attribute in ("start", "end")
            for test in (
                (
                    "time.peugeot_suv_3008_charging_time",
                    lambda vehicle_details: setattr(
                        vehicle_details.embedded.extension.onboard_capabilities.remote.charging,
                        "supported",
                        False,
                    ),
                ),
                (
                    f"time.peugeot_suv_3008_charging_program_5_{attribute}_time",
                    lambda vehicle_details: setattr(
                        vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                        "supported",
                        False,
                    ),
                ),
                (
                    f"time.peugeot_suv_3008_charging_program_1_{attribute}_time",
                    lambda vehicle_details: setattr(
                        vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                        "size",
                        0,
                    ),
                ),
                (
                    f"time.peugeot_suv_3008_charging_program_4_{attribute}_time",
                    lambda vehicle_details: setattr(
                        vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                        "size",
                        2,
                    ),
                ),
                (
                    f"time.peugeot_suv_3008_charging_program_5_{attribute}_time",
                    lambda vehicle_details: setattr(
                        vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                        "size",
                        None,
                    ),
                ),
            )
        ],
    ],
    indirect=["vehicle_details_mod_fn"],
)
async def test_no_actionable_entity_if_not_supported(
    entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test that no actionable time entities are created for a vehicle that does not support it."""
    assert not entity_registry.async_get(entity_id)


@pytest.mark.parametrize(
    ("entity_id", "vehicle_details_mod_fn"),
    [
        (
            "time.peugeot_suv_3008_preconditioning_program_1_start_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.preconditioning.parameters.programs,
                "size",
                None,
            ),
        ),
        (
            "time.peugeot_suv_3008_preconditioning_program_1_start_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension, "onboard_capabilities", None
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule,
                "next_delayed_time",
                None,
            ),
        ),
        (
            "time.peugeot_suv_3008_charging_time",
            lambda vehicle_details: setattr(
                vehicle_details.embedded.extension, "onboard_capabilities", None
            ),
        ),
        *[
            test
            for attribute in ("start", "end")
            for test in (
                (
                    f"time.peugeot_suv_3008_charging_program_1_{attribute}_time",
                    lambda vehicle_details: setattr(
                        vehicle_details.embedded.extension.onboard_capabilities.remote.charging.parameters.schedule.programs,
                        "size",
                        None,
                    ),
                ),
                (
                    f"time.peugeot_suv_3008_charging_program_1_{attribute}_time",
                    lambda vehicle_details: setattr(
                        vehicle_details.embedded.extension, "onboard_capabilities", None
                    ),
                ),
            )
        ],
    ],
    indirect=["vehicle_details_mod_fn"],
)
async def test_actionable_entity_unknown_supported_disabled(
    entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test that actionable time entities are created but it is disabled if the support is unknown."""
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
