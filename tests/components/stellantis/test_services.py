"""Test for Stellantis services."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import (
    ArrayOfChargingSchedules,
    ProgramRecurrence,
    RemotePostResponse,
    Status,
    Vehicle,
    WeekDays,
)
from stellantis.model.error import StellantisError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stellantis.const import (
    ATTR_ENABLED,
    ATTR_END,
    ATTR_OCCURRENCE,
    ATTR_POSITION,
    ATTR_PROGRAM_NUMBER,
    ATTR_RECURRENCE,
    ATTR_START,
    DOMAIN,
    SERVICE_DELETE_PRECONDITIONING_PROGRAM,
    SERVICE_SEND_NAVIGATION_POSITIONS,
    SERVICE_SET_CHARGING_PROGRAM,
    SERVICE_SET_PRECONDITIONING_PROGRAM,
    SERVICE_WAKE_UP,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import RESULT_EXCEPTION, RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("send_webhook_result")
@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (
            SERVICE_WAKE_UP,
            {},
        ),
        (
            SERVICE_DELETE_PRECONDITIONING_PROGRAM,
            {ATTR_PROGRAM_NUMBER: 3},
        ),
        (
            SERVICE_SEND_NAVIGATION_POSITIONS,
            {ATTR_POSITION: {ATTR_LATITUDE: 42.1225, ATTR_LONGITUDE: -6.71916667}},
        ),
        (
            SERVICE_SEND_NAVIGATION_POSITIONS,
            {
                ATTR_POSITION: {ATTR_LATITUDE: 42.1174431, ATTR_LONGITUDE: -6.7209368},
                f"{ATTR_POSITION}_1": {
                    ATTR_LATITUDE: 42.125106,
                    ATTR_LONGITUDE: -6.7016781,
                },
            },
        ),
        (
            SERVICE_SEND_NAVIGATION_POSITIONS,
            {
                ATTR_POSITION: {ATTR_LATITUDE: 1, ATTR_LONGITUDE: 1},
                f"{ATTR_POSITION}_9": {
                    ATTR_LATITUDE: 10,
                    ATTR_LONGITUDE: 10,
                },
            },
        ),
        (
            SERVICE_SEND_NAVIGATION_POSITIONS,
            {
                ATTR_POSITION: {ATTR_LATITUDE: 0, ATTR_LONGITUDE: 0},
                **{
                    f"{ATTR_POSITION}_{i}": {
                        ATTR_LATITUDE: i,
                        ATTR_LONGITUDE: i,
                    }
                    for i in range(1, 10)
                },
            },
        ),
    ],
)
async def test_service_call_remote_action_payload(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
    service: str,
    service_data: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Check the payloads from a successful service call."""
    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_DEVICE_ID: device_entry.id, **service_data},
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )


@pytest.mark.usefixtures("send_webhook_result")
async def test_partailly_edit_charging_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
    vehicle_status: Status,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the partial edit of a charging program."""
    slot = 1
    array_of_programs = vehicle_status.energies[1].extension.electric.charging.schedule
    assert isinstance(array_of_programs, ArrayOfChargingSchedules)
    assert array_of_programs.programs

    program = array_of_programs.programs[0]
    assert program
    assert program.start != "PT0S"

    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CHARGING_PROGRAM,
        {
            ATTR_DEVICE_ID: device_entry.id,
            ATTR_PROGRAM_NUMBER: slot,
            ATTR_START: "00:00",
            ATTR_ENABLED: False,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )

    # assert that the service hasn't overwritten any data
    assert program.start != "PT0S"


@pytest.mark.usefixtures("send_webhook_result")
async def test_fully_edit_preconditioning_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
    vehicle_status: Status,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the full edit of a preconditioning program."""
    slot = 1
    programs = vehicle_status.preconditioning.air_conditioning.programs
    assert programs

    program = None
    for p in programs:
        if p.slot == slot:
            program = p
            break
    assert program
    assert program.start != "PT0S"
    assert program.occurence  # codespell:ignore occurence
    assert set(program.occurence.day) != {  # codespell:ignore occurence
        WeekDays.MONDAY,
        WeekDays.WEDNESDAY,
    }
    assert program.recurrence != ProgramRecurrence.DAILY
    assert program.enabled

    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRECONDITIONING_PROGRAM,
        {
            ATTR_DEVICE_ID: device_entry.id,
            ATTR_PROGRAM_NUMBER: slot,
            ATTR_START: "00:00",
            ATTR_OCCURRENCE: ["mon", "wed"],
            ATTR_RECURRENCE: "daily",
            ATTR_ENABLED: False,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )

    # assert that the service hasn't overwritten any data
    assert program.start != "PT0S"


@pytest.mark.usefixtures("send_webhook_result")
async def test_partailly_edit_preconditioning_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
    vehicle_status: Status,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the partial edit of a preconditioning program."""
    slot = 1
    programs = vehicle_status.preconditioning.air_conditioning.programs
    assert programs

    program = None
    for p in programs:
        if p.slot == slot:
            program = p
            break
    assert program
    assert program.start != "PT0S"

    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRECONDITIONING_PROGRAM,
        {
            ATTR_DEVICE_ID: device_entry.id,
            ATTR_PROGRAM_NUMBER: slot,
            ATTR_START: "00:00",
            ATTR_ENABLED: False,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )

    # assert that the service hasn't overwritten any data
    assert program.start != "PT0S"


@pytest.mark.usefixtures("send_webhook_result")
async def test_create_charging_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
    snapshot: SnapshotAssertion,
) -> None:
    """Test create a charging program."""
    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CHARGING_PROGRAM,
        {
            ATTR_DEVICE_ID: device_entry.id,
            ATTR_START: "00:00",
            ATTR_OCCURRENCE: ["mon", "wed"],
            ATTR_END: "02:00",
            ATTR_ENABLED: False,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )


@pytest.mark.usefixtures("send_webhook_result")
async def test_create_preconditioning_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
    snapshot: SnapshotAssertion,
) -> None:
    """Test create a preconditioning program."""
    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRECONDITIONING_PROGRAM,
        {
            ATTR_DEVICE_ID: device_entry.id,
            ATTR_START: "00:00",
            ATTR_OCCURRENCE: ["mon", "wed"],
            ATTR_RECURRENCE: "daily",
            ATTR_ENABLED: False,
        },
        blocking=True,
    )

    client.send_remote_to_vhl.assert_called_once_with(
        vehicle_details.id, "mock-callback-id", snapshot
    )


async def test_device_not_found_exception(
    hass: HomeAssistant,
) -> None:
    """Test that trying to call an action with a unregistered device id raises an exception."""

    with pytest.raises(ServiceValidationError, match=r"Device.*not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WAKE_UP,
            {ATTR_DEVICE_ID: "A DEVICE ID"},
            blocking=True,
        )


async def test_different_domain_device_exception(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that trying to run a action with a device from other config entry raises an exception."""
    another_config_entry = MockConfigEntry(domain="ANOTHER_DOMAIN")
    another_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=another_config_entry.entry_id,
        identifiers={("ANOTHER_DOMAIN", "VINABCDE")},
    )

    with pytest.raises(ServiceValidationError, match=r"config entry.*not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WAKE_UP,
            {ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
        )


async def test_create_charging_program_missing_fields(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: Vehicle,
) -> None:
    """Test that trying to create a charging program with missing fields raises an exception."""
    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    with pytest.raises(ServiceValidationError, match=r"start.*field.*required"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CHARGING_PROGRAM,
            {
                ATTR_DEVICE_ID: device_entry.id,
                ATTR_OCCURRENCE: ["mon", "wed"],
                ATTR_ENABLED: False,
            },
            blocking=True,
        )


async def test_create_preconditioning_program_missing_fields(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: Vehicle,
) -> None:
    """Test that trying to create a preconditioning program with missing fields raises an exception."""
    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    with pytest.raises(ServiceValidationError, match=r"all fields.*required"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRECONDITIONING_PROGRAM,
            {
                ATTR_DEVICE_ID: device_entry.id,
                ATTR_OCCURRENCE: ["mon", "wed"],
                ATTR_RECURRENCE: "daily",
                ATTR_ENABLED: False,
            },
            blocking=True,
        )


async def test_edit_charging_program_missing_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: Vehicle,
) -> None:
    """Test that trying to edit a program raises an exception."""
    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    with pytest.raises(ServiceValidationError, match=r"Program.*not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CHARGING_PROGRAM,
            {
                ATTR_PROGRAM_NUMBER: 2,
                ATTR_DEVICE_ID: device_entry.id,
                ATTR_OCCURRENCE: ["mon", "wed"],
                ATTR_ENABLED: False,
            },
            blocking=True,
        )


async def test_edit_preconditioning_program_missing_program(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: Vehicle,
) -> None:
    """Test that trying to edit a program raises an exception."""
    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    with pytest.raises(ServiceValidationError, match=r"Program.*not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRECONDITIONING_PROGRAM,
            {
                ATTR_PROGRAM_NUMBER: 2,
                ATTR_DEVICE_ID: device_entry.id,
                ATTR_OCCURRENCE: ["mon", "wed"],
                ATTR_RECURRENCE: "daily",
                ATTR_ENABLED: False,
            },
            blocking=True,
        )


async def test_remote_request_failed_execution(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test an error on the remote request execution raises an exception."""
    client.send_remote_to_vhl.side_effect = StellantisError("A test error")

    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    with pytest.raises(
        HomeAssistantError, match=r"Execution.*remote action.*failed.*A test error"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WAKE_UP,
            {ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
        )


async def test_remote_request_missing_callback_id_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test a remote post response without remote action id does simply end the service call."""
    config_entry.runtime_data.callback_id = None

    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )
    with pytest.raises(HomeAssistantError, match=r"Callback.*not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WAKE_UP,
            {ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
        )
    client.send_remote_to_vhl.assert_not_awaited()


async def test_remote_request_missing_remote_action_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test a remote post response without remote action id does simply end the service call."""
    client.send_remote_to_vhl.return_value = RemotePostResponse()

    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_WAKE_UP,
        {ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )


async def test_remote_action_callback_timeout(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: Vehicle,
) -> None:
    """Test the case were a "Done" response is not received within the timeout period."""
    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    with patch(
        "homeassistant.components.stellantis.webhook.StellantisCallbackEvent.__await__",
        side_effect=TimeoutError(),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WAKE_UP,
            {ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
        )


@pytest.mark.parametrize(
    "send_webhook_result",
    [
        [RESULT_SUCCESS],
        [RESULT_PENDING, RESULT_SUCCESS],
        [RESULT_EXCEPTION, RESULT_SUCCESS],
    ],
    indirect=True,
)
async def test_remote_request_success_result(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
    send_webhook_result: None,
) -> None:
    """Test if a remote request result is pending and then is done doesn't break anything."""
    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_WAKE_UP,
        {ATTR_DEVICE_ID: device_entry.id},
        blocking=True,
    )


@pytest.mark.parametrize(
    "send_webhook_result",
    [[RESULT_FAILED], [RESULT_PENDING, RESULT_FAILED]],
    indirect=True,
)
async def test_remote_request_failed_result(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: Vehicle,
    send_webhook_result: None,
) -> None:
    """Test a failed remote request raises an exception."""

    assert vehicle_details.vin
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    with pytest.raises(
        HomeAssistantError, match=r"Remote action.*failed.*GeneralError"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WAKE_UP,
            {ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
        )
