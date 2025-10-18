"""Stellantis switch platform."""

from dataclasses import dataclass
from functools import partial

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


def _check_vehicles_and_add_entities(
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    known_vehicles: set[str],
) -> None:
    coordinator_data = entry.runtime_data.coordinator.data
    current_vehicles = set(coordinator_data.keys())
    new_vehicles = current_vehicles - known_vehicles
    no_longer_known_vehicles = known_vehicles - current_vehicles
    for vin in no_longer_known_vehicles:
        known_vehicles.remove(vin)
    known_vehicles.update(new_vehicles)

    entities: list[StellantisLights] = []
    for vehicle_vin in new_vehicles:
        vehicle_coordinator = coordinator_data[vehicle_vin]

        if (
            lights_supported := (
                embedded.extension.onboard_capabilities.remote.lights.supported
                if (embedded := vehicle_coordinator.vehicle.embedded)
                and embedded.extension
                and embedded.extension.onboard_capabilities
                and embedded.extension.onboard_capabilities.remote
                else None
            )
        ) is not False:
            entities.append(
                StellantisLights(
                    vehicle_coordinator,
                    LIGHTS_ENTITY_DESCRIPTION,
                    lights_supported is None,
                )
            )

    if entities:
        async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StellantisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""
    known_vehicles: set[str] = set()

    entry.async_on_unload(
        entry.runtime_data.coordinator.async_add_listener(
            partial(
                _check_vehicles_and_add_entities,
                entry,
                async_add_entities,
                known_vehicles,
            )
        )
    )


class StellantisLights(LightEntity, StellantisToggleEntity):
    """Representation of Stellantis vehicle lights."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    entity_description: StellantisLightEntityDescription
