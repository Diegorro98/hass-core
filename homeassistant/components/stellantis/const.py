"""Stellantis constants."""

from enum import StrEnum

DOMAIN = "stellantis"

API_ENDPOINT = "https://api.groupe-psa.com/connectedcar/v4"

CONF_BRAND = "brand"


class Brand(StrEnum):
    """Stellantis brands."""

    CITROEN = "Citroen"
    DS = "DS"
    OPEL = "Opel"
    PEUGEOT = "Peugeot"
    VAUXHALL = "Vauxhall"
