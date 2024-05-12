"""Handle Stellantis service calls."""

from asyncio import timeout
from datetime import timedelta
from typing import Any

from jsonpath import jsonpath
from stringcase import sentencecase
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from .api import StellantisVehicle
from .const import (
    ATTR_DAILY_RECURRENCE,
    ATTR_ENABLED,
    ATTR_EVENT_TYPE,
    ATTR_FAILURE_CAUSE,
    ATTR_OCCURRENCE,
    ATTR_POSITION,
    ATTR_PROGRAM_NUMBER,
    ATTR_REMOTE_ACTION_ID,
    ATTR_START,
    ATTR_STATUS,
    CONF_CALLBACK_ID,
    DOMAIN,
    LOGGER,
    SERVICE_DELETE_PRECONDITIONING_PROGRAM,
    SERVICE_SEND_NAVIGATION_POSITIONS,
    SERVICE_SET_PRECONDITIONING_PROGRAM,
    SERVICE_WAKE_UP,
    EventStatusType,
    RemoteDoneEventStatus,
)
from .coordinator import StellantisUpdateCoordinator
from .helpers import preconditioning_program_setter_body
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


async def async_send_remote_requests(
    hass: HomeAssistant,
    call: ServiceCall,
    request_body: dict[str, Any],
    service_name: str,
) -> None:
    """Send a remote request to the API and wait for the confirmation."""
    device_id = call.data.get(ATTR_DEVICE_ID)
    if device_id is None:
        raise HomeAssistantError("Device ID not provided")
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Device not found: {device_id}")
    device_vin = device.identifiers.copy().pop()[1]

    config_entry_id = device.config_entries.copy().pop()
    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    if config_entry is None:
        raise HomeAssistantError("Config entry not found")
    if CONF_CALLBACK_ID not in config_entry.data:
        raise HomeAssistantError(
            "Callback has not been setup, probably because external URL is not configured"
        )
    callback_id = config_entry.data[CONF_CALLBACK_ID]
    coordinator: StellantisUpdateCoordinator = hass.data[DOMAIN][
        config_entry_id
    ].coordinator

    vehicle: StellantisVehicle | None = None
    for vehicle_to_check in coordinator.data:
        if vehicle_to_check.details.vin == device_vin:
            vehicle = vehicle_to_check
            break

    if vehicle is None:
        raise HomeAssistantError(f"Vehicle not found: {device_vin}")

    async with timeout(10):
        response_data = await coordinator.api.async_send_remote_action(
            vehicle.details.id,
            callback_id,
            request_body,
        )

    if ATTR_REMOTE_ACTION_ID not in response_data:
        LOGGER.warning(
            f"The {service_name} service result will not be tracked as the remote action ID is missing from the API response"
        )
        return

    try:
        async with timeout(10):
            while True:
                with StellantisCallbackEvent(
                    hass, response_data[ATTR_REMOTE_ACTION_ID]
                ) as callback_event:
                    event_status = await callback_event
                    match event_status[ATTR_EVENT_TYPE]:
                        case EventStatusType.PENDING:
                            LOGGER.debug(
                                "Pending notification received from remote action, reason: %s",
                                event_status.get(ATTR_STATUS, "Not specified"),
                            )
                            continue
                        case EventStatusType.DONE:
                            match event_status[ATTR_STATUS]:
                                case RemoteDoneEventStatus.FAILED:
                                    raise HomeAssistantError(
                                        f"Remote action failed. Cause: {event_status[ATTR_FAILURE_CAUSE]}"
                                    )
                    break
    except TimeoutError:
        LOGGER.warning(
            f"Status notification for {service_name} service was not received in time"
        )


def transform_to_stellantis_time_schema(time: timedelta) -> str:
    """Transform time to ISO 8601 with the schema: P[n]Y[n]M[n]DT[n]H[n]M[n]S."""
    return f"PT{time.seconds // 3600}H{time.seconds % 3600 // 60}M"


async def async_setup_hass_services(hass: HomeAssistant) -> None:
    """Set up services for Stellantis."""

    async def async_delete_preconditioning_program_service(call: ServiceCall) -> None:
        """Handle the service call."""
        await async_send_remote_requests(
            hass,
            call,
            {
                "preconditioning": {
                    "airConditioning": {
                        "programs": [
                            {
                                "slot": call.data[ATTR_PROGRAM_NUMBER],
                                "actionsType": "Delete",
                            }
                        ]
                    }
                }
            },
            SERVICE_DELETE_PRECONDITIONING_PROGRAM,
        )

    async def async_set_navigation_positions_service(call: ServiceCall) -> None:
        """Handle the service call."""
        positions = [
            {
                "coordinates": [
                    call.data[ATTR_POSITION][ATTR_LATITUDE],
                    call.data[ATTR_POSITION][ATTR_LONGITUDE],
                ],
                "type": "Point",
            }
        ] + [
            {
                "coordinates": [
                    call.data[f"{ATTR_POSITION}_{x}"][ATTR_LATITUDE],
                    call.data[f"{ATTR_POSITION}_{x}"][ATTR_LONGITUDE],
                ],
                "type": "Point",
            }
            for x in range(1, 10)
            if f"{ATTR_POSITION}_{x}" in call.data
        ]
        await async_send_remote_requests(
            hass,
            call,
            {"navigation": {"positions": positions}},
            SERVICE_SEND_NAVIGATION_POSITIONS,
        )

    async def async_set_preconditioning_program_service(call: ServiceCall) -> None:
        """Handle the service call."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        if device_id is None:
            raise HomeAssistantError("Device ID not provided")
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if device is None:
            raise HomeAssistantError(f"Device not found: {device_id}")
        device_vin = device.identifiers.copy().pop()[1]

        config_entry_id = device.config_entries.copy().pop()
        config_entry = hass.config_entries.async_get_entry(config_entry_id)
        if config_entry is None:
            raise HomeAssistantError("Config entry not found")
        coordinator: StellantisUpdateCoordinator = hass.data[DOMAIN][
            config_entry_id
        ].coordinator

        vehicle_status = None
        for vehicle in coordinator.data:
            if vehicle.details.vin == device_vin:
                vehicle_status = vehicle.status
                break
        if vehicle_status is None:
            raise HomeAssistantError(f"Vehicle status not found: {device_vin}")

        programs: list[dict[str, Any]] = jsonpath(
            vehicle_status,
            "$.preconditioning.airConditioning.programs[*]",
        )
        if not programs:
            raise HomeAssistantError("Preconditioning programs not found")

        program_to_set = None
        for program in programs:
            if program["slot"] == call.data[ATTR_PROGRAM_NUMBER]:
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
                raise HomeAssistantError(
                    "To create a new program, all fields are required"
                )
            program_to_set = {"slot": call.data[ATTR_PROGRAM_NUMBER]}

        if ATTR_START in call.data:
            program_to_set[ATTR_START] = transform_to_stellantis_time_schema(
                call.data[ATTR_START]
            )
        if ATTR_OCCURRENCE in call.data:
            program_to_set["occurence"] = {  # codespell:ignore occurence
                "day": [sentencecase(weekday) for weekday in call.data[ATTR_OCCURRENCE]]
            }
        if ATTR_DAILY_RECURRENCE in call.data:
            program_to_set["recurrence"] = (
                "Daily" if call.data[ATTR_DAILY_RECURRENCE] else "None"
            )
        if ATTR_ENABLED in call.data:
            program_to_set[ATTR_ENABLED] = call.data[ATTR_ENABLED]

        await async_send_remote_requests(
            hass,
            call,
            preconditioning_program_setter_body(program_to_set),
            SERVICE_SET_PRECONDITIONING_PROGRAM,
        )

    async def async_wake_up_vehicle_service(call: ServiceCall) -> None:
        """Handle the service call."""
        await async_send_remote_requests(
            hass, call, {"wakeUp": {"action": "WakeUp"}}, SERVICE_WAKE_UP
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
