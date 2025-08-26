"""Stellantis switch platform."""

from dataclasses import dataclass

from stellantis.model import Remote, RemoteHorn, RemoteHornState

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StellantisConfigEntry
from .entity import StellantisToggleEntity, StellantisToggleEntityDescription


@dataclass(frozen=True, kw_only=True)
class StellantisSirenEntityDescription(
    SirenEntityDescription, StellantisToggleEntityDescription
):
    """Siren entity description."""


HORN_ENTITY_DESCRIPTION = StellantisSirenEntityDescription(
    key="horn",
    translation_key="horn",
    remote_request_on=Remote(horn=RemoteHorn(state=RemoteHornState.ACTIVATED)),
    remote_request_off=Remote(horn=RemoteHorn(state=RemoteHornState.UNACTIVATED)),
    value_fn=lambda _: None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""

    async_add_entities(
        StellantisHorn(hass, vehicle_coordinator, HORN_ENTITY_DESCRIPTION, entry)
        for vehicle_coordinator in entry.runtime_data
    )


class StellantisHorn(StellantisToggleEntity, SirenEntity):
    """Representation of Stellantis vehicle horn."""

    entity_description: StellantisSirenEntityDescription
    attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
