"""Stellantis constants."""

from enum import StrEnum
import logging

CONF_BRAND = "brand"
CONF_CALLBACK_ID = "callback_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"

ATTR_ALTITUDE = "altitude"
ATTR_ENABLED = "enabled"
ATTR_HEADING = "heading"
ATTR_OCCURRENCE = "occurrence"
ATTR_POSITION = "position"
ATTR_PROGRAM_NUMBER = "program_number"
ATTR_RECURRENCE = "recurrence"
ATTR_START = "start"
DOMAIN = "stellantis"

REMOTE_DONE_EVENT_STATUS_FAILED = "Failed"

SERVICE_DELETE_PRECONDITIONING_PROGRAM = "delete_preconditioning_program"
SERVICE_SEND_NAVIGATION_POSITIONS = "send_navigation_positions"
SERVICE_SET_PRECONDITIONING_PROGRAM = "set_preconditioning_program"
SERVICE_WAKE_UP = "wake_up"

SVE_TRANSLATION_PLACEHOLDER_SLOT = "slot"

LOGGER = logging.getLogger(__package__)


class Brand(StrEnum):
    """Stellantis brands."""

    CITROEN = "Citroen"
    DS = "DS"
    OPEL = "Opel"
    PEUGEOT = "Peugeot"
    VAUXHALL = "Vauxhall"


class RemoteDoneEventStatus(StrEnum):
    """Event status for Done remote notifications."""

    ALREADY_DONE = "AlreadyDone"
    FAILED = "Failed"
    SUCCESS = "Success"
