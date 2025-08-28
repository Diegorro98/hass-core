"""Handle Stellantis service calls."""

from asyncio import timeout
import copy
from typing import Any, cast

from stellantis.model import (
    ActionType,
    AirConditioningProgram,
    Point,
    PreconditioningProgram,
    ProgramRecurrence,
    Remote,
    RemoteEventType,
    RemoteNavigation,
    RemotePreconditioning,
    RemotePreconditioningAirConditioning,
    RemoteWakeUp,
    WeekDays,
    WeekOccurrence,
)
from stellantis.model.error import StellantisError
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

from .const import (
    ATTR_ENABLED,
    ATTR_OCCURRENCE,
    ATTR_POSITION,
    ATTR_PROGRAM_NUMBER,
    ATTR_RECURRENCE,
    ATTR_START,
    CONF_CALLBACK_ID,
    DOMAIN,
    LOGGER,
    SERVICE_DELETE_PRECONDITIONING_PROGRAM,
    SERVICE_SEND_NAVIGATION_POSITIONS,
    SERVICE_SET_PRECONDITIONING_PROGRAM,
    SERVICE_WAKE_UP,
    RemoteDoneEventStatus,
)
from .coordinator import StellantisConfigEntry, StellantisVehicleCoordinator
from .helpers import preconditioning_program_setter_body, time_to_iso_duration
from .webhook import StellantisCallbackEvent

SCHEDULE_SCHEMA: dict[vol.Marker, Any] = {
    vol.Optional(ATTR_ENABLED): cv.boolean,
    vol.Optional(ATTR_START): cv.time_period_str,
    vol.Optional(ATTR_OCCURRENCE): cv.weekdays,
}

POSITION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_LATITUDE): cv.latitude,
        vol.Required(ATTR_LONGITUDE): cv.longitude,
    }
)


def _get_vehicle_coordinator_and_callback_id(
    call: ServiceCall,
) -> tuple[StellantisVehicleCoordinator, str]:
    hass = call.hass
    device_id = call.data[ATTR_DEVICE_ID]
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="action_device_not_found",
            translation_placeholders={"device_id": device_id},
        )

    config_entry: StellantisConfigEntry | None = None
    for entry_id in device.config_entries:
        _config_entry = hass.config_entries.async_get_entry(entry_id)
        assert _config_entry
        if _config_entry.domain == DOMAIN:
            config_entry = cast(StellantisConfigEntry, _config_entry)
            break
    if config_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="action_config_entry_not_found",
            translation_placeholders={"device_id": device_id},
        )

    device_vin = next(
        (identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN),
    )
    vehicle_coordinator: StellantisVehicleCoordinator | None = None
    for _vehicle_coordinator in config_entry.runtime_data:
        if _vehicle_coordinator.vehicle.vin == device_vin:
            vehicle_coordinator = _vehicle_coordinator
            break
    assert vehicle_coordinator

    return vehicle_coordinator, config_entry.data[CONF_CALLBACK_ID]


async def _async_send_remote_requests(
    call: ServiceCall,
    remote: Remote,
    service_name: str,
    vehicle_coordinator: StellantisVehicleCoordinator | None = None,
    callback_id: str | None = None,
) -> None:
    """Send a remote request to the API and wait for the confirmation."""

    if not vehicle_coordinator or not callback_id:
        _vehicle_coordinator, _callback_id = _get_vehicle_coordinator_and_callback_id(
            call
        )
    else:
        _vehicle_coordinator = vehicle_coordinator
        _callback_id = callback_id

    try:
        assert _vehicle_coordinator.vehicle.id
        response_data = await _vehicle_coordinator.client.send_remote_to_vhl(
            _vehicle_coordinator.vehicle.id,
            _callback_id,
            remote,
        )
    except StellantisError as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="executing_remote_request_failed",
            translation_placeholders={"failure_cause": str(e) or "Not specified"},
        ) from e

    if not response_data.remote_action_id:
        LOGGER.warning(
            f"The 'stellantis.{service_name}' service result will not be tracked as the remote action ID is missing from the API response"
        )
        return

    try:
        async with timeout(10):
            while True:
                with StellantisCallbackEvent(
                    call.hass, response_data.remote_action_id
                ) as callback_event:
                    event_status = await callback_event
                    assert event_status.type == RemoteEventType.DONE
                    match event_status.status:
                        case RemoteDoneEventStatus.FAILED:
                            raise HomeAssistantError(
                                translation_domain=DOMAIN,
                                translation_key="remote_request_failed",
                                translation_placeholders={
                                    "failure_cause": event_status.failure_cause
                                    or "Not specified"
                                },
                            )
                    break
    except TimeoutError:
        LOGGER.warning(
            f"Status notification for 'stellantis.{service_name}' service was not received in time"
        )


async def async_delete_preconditioning_program_service(call: ServiceCall) -> None:
    """Handle the service call."""
    await _async_send_remote_requests(
        call,
        Remote(
            preconditioning=RemotePreconditioning(
                air_conditioning=RemotePreconditioningAirConditioning(
                    programs=[
                        AirConditioningProgram(
                            start="PT0S",
                            slot=call.data[ATTR_PROGRAM_NUMBER],
                            actions_type=ActionType.DELETE,
                        )
                    ]
                )
            )
        ),
        SERVICE_DELETE_PRECONDITIONING_PROGRAM,
    )


async def async_set_navigation_positions_service(call: ServiceCall) -> None:
    """Handle the service call."""
    positions = [
        Point(
            coordinates=[
                (position := call.data[ATTR_POSITION])[ATTR_LATITUDE],
                position[ATTR_LONGITUDE],
            ]
        )
    ]
    positions.extend(
        Point(
            coordinates=[position[ATTR_LATITUDE], position[ATTR_LONGITUDE]],
        )
        for key, position in dict(sorted(call.data.items())).items()
        if key.startswith(f"{ATTR_POSITION}_")
    )
    await _async_send_remote_requests(
        call,
        Remote(navigation=RemoteNavigation(positions=positions)),
        SERVICE_SEND_NAVIGATION_POSITIONS,
    )


async def async_set_preconditioning_program_service(call: ServiceCall) -> None:
    """Handle the service call."""
    vehicle_coordinator, callback_id = _get_vehicle_coordinator_and_callback_id(call)

    if (
        vehicle_coordinator.data.preconditioning
        and vehicle_coordinator.data.preconditioning.air_conditioning
    ):
        programs = vehicle_coordinator.data.preconditioning.air_conditioning.programs

    program_to_set = None
    slot = call.data.get(ATTR_PROGRAM_NUMBER)
    all_filled = all(
        attr in call.data
        for attr in (
            ATTR_ENABLED,
            ATTR_START,
            ATTR_OCCURRENCE,
            ATTR_RECURRENCE,
        )
    )
    if slot is None or all_filled:
        # If there's no slot, a new program is created.
        # If there's slot and all the fields are filled
        # we don't need to search for the program to update it
        # as all the fields are going to be overwritten.
        if not all_filled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="action_new_preconditioning_program_missing_fields",
            )
        program_to_set = PreconditioningProgram(
            slot=slot,
            start=time_to_iso_duration(call.data[ATTR_START]),
            enabled=call.data[ATTR_ENABLED],
        )

    else:
        # Find the existing program to update
        for program in programs or []:
            if program.slot == slot:
                program_to_set = copy.deepcopy(program)
                break
        if not program_to_set:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="action_program_not_found",
                translation_placeholders={"slot": str(slot)},
            )
        if ATTR_START in call.data:
            program_to_set.start = time_to_iso_duration(call.data[ATTR_START])
        if ATTR_ENABLED in call.data:
            program_to_set.enabled = call.data[ATTR_ENABLED]
    if ATTR_OCCURRENCE in call.data:
        program_to_set.occurence = WeekOccurrence(  # codespell:ignore occurence
            day=[
                WeekDays(day.capitalize())
                for day in cast(list[str], call.data[ATTR_OCCURRENCE])
            ]
        )
    if ATTR_RECURRENCE in call.data:
        program_to_set.recurrence = ProgramRecurrence(
            cast(str, call.data[ATTR_RECURRENCE]).capitalize()
        )

    await _async_send_remote_requests(
        call,
        preconditioning_program_setter_body(program_to_set),
        SERVICE_SET_PRECONDITIONING_PROGRAM,
        vehicle_coordinator,
        callback_id,
    )


async def async_wake_up_vehicle_service(call: ServiceCall) -> None:
    """Handle the service call."""
    await _async_send_remote_requests(
        call, Remote(wake_up=RemoteWakeUp()), SERVICE_WAKE_UP
    )


async def async_setup_hass_services(hass: HomeAssistant) -> None:
    """Set up services for Stellantis."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_PRECONDITIONING_PROGRAM,
        async_delete_preconditioning_program_service,
        vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_PROGRAM_NUMBER): vol.In(range(1, 5)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_NAVIGATION_POSITIONS,
        async_set_navigation_positions_service,
        vol.Schema(
            cast(
                dict[vol.Marker, Any],
                {
                    vol.Required(ATTR_DEVICE_ID): cv.string,
                    vol.Required(ATTR_POSITION): POSITION_SCHEMA,
                    **{
                        vol.Optional(f"{ATTR_POSITION}_{x}"): POSITION_SCHEMA
                        for x in range(1, 10)
                    },
                },
            )
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PRECONDITIONING_PROGRAM,
        async_set_preconditioning_program_service,
        vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Optional(ATTR_PROGRAM_NUMBER): vol.In(range(1, 5)),
                **SCHEDULE_SCHEMA,
                vol.Optional(ATTR_RECURRENCE): vol.In(
                    [slugify(val) for val in ProgramRecurrence.__members__.values()]
                ),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_WAKE_UP,
        async_wake_up_vehicle_service,
        vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string}),
    )
