"""Stellantis constants."""

from enum import StrEnum
import logging

API_ENDPOINT = "https://api.groupe-psa.com/connectedcar/v4"

CONF_BRAND = "brand"
CONF_CALLBACK_ID = "callback_id"

ATTR_ALTITUDE = "altitude"
ATTR_CHARGING_POWER_LEVEL = "charging_power_level"
ATTR_ENABLED = "enabled"
ATTR_EVENT_STATUS = "eventStatus"
ATTR_EVENT_TYPE = "type"
ATTR_EVENT_TYPE_DONE = "Done"
ATTR_FAILURE_CAUSE = "failureCause"
ATTR_HEADING = "heading"
ATTR_TIME = "time"
ATTR_OCCURRENCE = "occurrence"
ATTR_POSITION = "position"
ATTR_PROGRAM_NUMBER = "program_number"
ATTR_DAILY_RECURRENCE = "daily_recurrence"
ATTR_REMOTE_ACTION_ID = "remoteActionId"
ATTR_REMOTE_EVENT = "remoteEvent"
ATTR_REMOTE_DONE_EVENT_STATUS = "RemoteDoneEventStatus"
ATTR_REMOTE_PENDING_EVENT_STATUS = "RemotePendingEventStatus"
ATTR_STATUS = "status"
ATTR_START = "start"
ATTR_SIGNAL_QUALITY = "signal_quality"

DOMAIN = "stellantis"

REMOTE_DONE_EVENT_STATUS_FAILED = "Failed"

SERVICE_DELETE_PRECONDITIONING_PROGRAM = "delete_preconditioning_program"
SERVICE_SEND_NAVIGATION_POSITIONS = "send_navigation_positions"
SERVICE_SET_CHARGING_POWER_LEVEL = "set_charging_power_level"
SERVICE_SET_NEXT_CHARGING_TIME = "set_next_charging_time"
SERVICE_SET_PRECONDITIONING_PROGRAM = "set_preconditioning_program"
SERVICE_WAKE_UP = "wake_up"

LOGGER = logging.getLogger(__package__)


class Brand(StrEnum):
    """Stellantis brands."""

    CITROEN = "Citroen"
    DS = "DS"
    OPEL = "Opel"
    PEUGEOT = "Peugeot"
    VAUXHALL = "Vauxhall"
