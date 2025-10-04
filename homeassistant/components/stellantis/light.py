"""Stellantis switch platform."""

from dataclasses import dataclass

from stellantis.model import Remote, RemoteLights

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StellantisConfigEntry
from .entity import StellantisToggleEntity, StellantisToggleEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class StellantisLightEntityDescription(
    StellantisToggleEntityDescription,
    LightEntityDescription,
):
    """Light entity description."""


LIGHTS_ENTITY_DESCRIPTION = StellantisLightEntityDescription(
    key="lights",
    translation_key="lights",
    value_fn=lambda _: None,
    remote_request_on=Remote(lights=RemoteLights(on=True)),
    remote_request_off=Remote(lights=RemoteLights(on=False)),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""
    async_add_entities(
        StellantisLights(
            vehicle_coordinator,
            LIGHTS_ENTITY_DESCRIPTION,
            lights_supported is None,
        )
        for vehicle_coordinator in entry.runtime_data.vehicle_coordinators
        if (
            lights_supported := (
                embedded.extension.onboard_capabilities.remote.lights.supported
                if (embedded := vehicle_coordinator.vehicle.embedded)
                and embedded.extension
                and embedded.extension.onboard_capabilities
                and embedded.extension.onboard_capabilities.remote
                else None
            )
        )
        is not False
    )


class StellantisLights(LightEntity, StellantisToggleEntity):
    """Representation of Stellantis vehicle lights."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    entity_description: StellantisLightEntityDescription
