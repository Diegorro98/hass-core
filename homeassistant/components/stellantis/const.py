"""Stellantis constants."""

from datetime import timedelta
from enum import StrEnum
import logging

VEHICLES_UPDATE_INTERVAL = timedelta(hours=1)
UPDATE_INTERVAL = timedelta(seconds=60)

CONF_BRAND = "brand"
CONF_CLOUDHOOK_URL = "cloudhook_url"

ATTR_ENABLED = "enabled"
ATTR_END = "end"
ATTR_OCCURRENCE = "occurrence"
ATTR_POSITION = "position"
ATTR_PROGRAM_NUMBER = "program_number"
ATTR_RECURRENCE = "recurrence"
ATTR_START = "start"
DOMAIN = "stellantis"

SERVICE_DELETE_PRECONDITIONING_PROGRAM = "delete_preconditioning_program"
SERVICE_SEND_NAVIGATION_POSITIONS = "send_navigation_positions"
SERVICE_SET_CHARGING_PROGRAM = "set_charging_program"
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


class RemoteDoneEventStatus(StrEnum):
    """Event status for Done remote notifications."""

    ALREADY_DONE = "AlreadyDone"
    FAILED = "Failed"
    SUCCESS = "Success"
