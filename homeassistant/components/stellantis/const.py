"""Stellantis constants."""

from enum import StrEnum
import logging

API_ENDPOINT = "https://api.groupe-psa.com/connectedcar/v4"

ATTR_ALTITUDE = "altitude"
ATTR_HEADING = "heading"
ATTR_SIGNAL_QUALITY = "signal_quality"

DOMAIN = "stellantis"

CONF_BRAND = "brand"

LOGGER = logging.getLogger(__package__)


class Brand(StrEnum):
    """Stellantis brands."""

    CITROEN = "Citroen"
    DS = "DS"
    OPEL = "Opel"
    PEUGEOT = "Peugeot"
    VAUXHALL = "Vauxhall"
