"""Handle Stellantis service calls."""

from asyncio import timeout
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
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_DAILY_RECURRENCE,
    ATTR_ENABLED,
    ATTR_OCCURRENCE,
    ATTR_POSITION,
    ATTR_PROGRAM_NUMBER,
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

SVE_TRANSLATION_PLACEHOLDER_CONFIG_ENTRY_ID = "config_entry_id"
SVE_TRANSLATION_PLACEHOLDER_DEVICE_ID = "device_id"
SVE_TRANSLATION_PLACEHOLDER_VIN = "vin"

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


async def async_send_remote_requests(
    hass: HomeAssistant,
    call: ServiceCall,
    remote: Remote,
    service_name: str,
) -> None:
    """Send a remote request to the API and wait for the confirmation."""
    device_id = call.data[ATTR_DEVICE_ID]
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="remote_request_device_not_found",
            translation_placeholders={SVE_TRANSLATION_PLACEHOLDER_DEVICE_ID: device_id},
        )
    device_vin = device.identifiers.copy().pop()[1]

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
            translation_key="config_entry_not_found",
            translation_placeholders={"device_id": device_id},
        )
    callback_id = config_entry.data.get(CONF_CALLBACK_ID)
    if not callback_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="remote_request_callback_not_found",
            translation_placeholders={
                SVE_TRANSLATION_PLACEHOLDER_CONFIG_ENTRY_ID: config_entry.entry_id
            },
        )

    vehicle_coordinator: StellantisVehicleCoordinator | None = None
    for _vehicle_coordinator in config_entry.runtime_data:
        if _vehicle_coordinator.vehicle.vin == device_vin:
            vehicle_coordinator = _vehicle_coordinator
            break

    if vehicle_coordinator is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="remote_request_vehicle_not_found",
            translation_placeholders={SVE_TRANSLATION_PLACEHOLDER_VIN: device_vin},
        )

    async with timeout(10):
        assert vehicle_coordinator.vehicle.id
        response_data = await vehicle_coordinator.client.send_remote_to_vhl(
            vehicle_coordinator.vehicle.id,
            callback_id,
            remote,
        )

    if not response_data.remote_action_id:
        LOGGER.warning(
            f"The 'stellantis.{service_name}' service result will not be tracked as the remote action ID is missing from the API response"
        )
        return

    try:
        async with timeout(10):
            while True:
                with StellantisCallbackEvent(
                    hass, response_data.remote_action_id
                ) as callback_event:
                    event_status = await callback_event
                    match event_status.type:
                        case RemoteEventType.PENDING:
                            LOGGER.debug(
                                "Pending notification received from remote action, reason: %s",
                                event_status.status or "Not specified",
                            )
                            continue
                        case RemoteEventType.DONE:
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


async def async_setup_hass_services(hass: HomeAssistant) -> None:
    """Set up services for Stellantis."""

    async def async_delete_preconditioning_program_service(call: ServiceCall) -> None:
        """Handle the service call."""
        await async_send_remote_requests(
            hass,
            call,
            Remote(
                preconditioning=RemotePreconditioning(
                    air_conditioning=RemotePreconditioningAirConditioning(
                        programs=[
                            AirConditioningProgram(
                                start="PT0H0M",
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
        await async_send_remote_requests(
            hass,
            call,
            Remote(navigation=RemoteNavigation(positions=positions)),
            SERVICE_SEND_NAVIGATION_POSITIONS,
        )

    async def async_set_preconditioning_program_service(call: ServiceCall) -> None:
        """Handle the service call."""
        device_id = call.data[ATTR_DEVICE_ID]
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if device is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="remote_request_device_not_found",
                translation_placeholders={
                    SVE_TRANSLATION_PLACEHOLDER_DEVICE_ID: device_id
                },
            )
        device_vin = device.identifiers.copy().pop()[1]

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
                translation_key="config_entry_not_found",
                translation_placeholders={"device_id": device_id},
            )

        vehicle_coordinator: StellantisVehicleCoordinator | None = None
        for _vehicle_coordinator in config_entry.runtime_data:
            if _vehicle_coordinator.vehicle.vin == device_vin:
                vehicle_coordinator = _vehicle_coordinator
                break

        if vehicle_coordinator is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="remote_request_vehicle_not_found",
                translation_placeholders={SVE_TRANSLATION_PLACEHOLDER_VIN: device_vin},
            )

        if (
            not vehicle_coordinator.data.preconditioning
            or not vehicle_coordinator.data.preconditioning.air_conditioning
            or (
                programs
                := vehicle_coordinator.data.preconditioning.air_conditioning.programs
            )
            is None
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="remote_request_preconditioning_programs_not_found",
                translation_placeholders={
                    "vehicle_name": device.name or "Unknown",
                    SVE_TRANSLATION_PLACEHOLDER_VIN: device_vin,
                },
            )

        program_to_set = None
        for program in programs:
            if program.slot == call.data[ATTR_PROGRAM_NUMBER]:
                program_to_set = program
                break
        if program_to_set is None:
            if not all(
                attr in call.data
                for attr in (
                    ATTR_ENABLED,
                    ATTR_START,
                    ATTR_OCCURRENCE,
                    ATTR_DAILY_RECURRENCE,
                )
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="remote_request_new_preconditioning_program_missing_fields",
                )
            program_to_set = PreconditioningProgram(
                start=time_to_iso_duration(call.data[ATTR_START]),
                enabled=call.data[ATTR_ENABLED],
            )

        else:
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
        if ATTR_DAILY_RECURRENCE in call.data:
            program_to_set.recurrence = (
                ProgramRecurrence.DAILY
                if call.data[ATTR_DAILY_RECURRENCE]
                else ProgramRecurrence.NONE
            )

        await async_send_remote_requests(
            hass,
            call,
            preconditioning_program_setter_body(program_to_set),
            SERVICE_SET_PRECONDITIONING_PROGRAM,
        )

    async def async_wake_up_vehicle_service(call: ServiceCall) -> None:
        """Handle the service call."""
        await async_send_remote_requests(
            hass, call, Remote(wake_up=RemoteWakeUp()), SERVICE_WAKE_UP
        )

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

    navigation_positions_schema: dict[vol.Marker, Any] = {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_POSITION): POSITION_SCHEMA,
    }
    for x in range(1, 10):
        navigation_positions_schema[vol.Optional(f"{ATTR_POSITION}_{x}")] = (
            POSITION_SCHEMA
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_NAVIGATION_POSITIONS,
        async_set_navigation_positions_service,
        vol.Schema(navigation_positions_schema, extra=vol.ALLOW_EXTRA),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PRECONDITIONING_PROGRAM,
        async_set_preconditioning_program_service,
        vol.Schema(
            {
                vol.Required(ATTR_DEVICE_ID): cv.string,
                vol.Required(ATTR_PROGRAM_NUMBER): vol.In(range(1, 5)),
                **SCHEDULE_SCHEMA,
                vol.Optional(ATTR_DAILY_RECURRENCE): cv.boolean,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_WAKE_UP,
        async_wake_up_vehicle_service,
        vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string}),
    )
