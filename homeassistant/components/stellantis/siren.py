"""Stellantis switch platform."""

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantStellantisData
from .const import DOMAIN
from .coordinator import StellantisUpdateCoordinator, VehicleData
from .entity import StellantisBaseToggleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Stellantis switches."""

    data: HomeAssistantStellantisData = hass.data[DOMAIN][entry.entry_id]

    # In the future, when "onboardCapabilities" extension header works, we will know
    # whether to add the horn if the vehicle has the capability to honk the horn
    async_add_entities(
        StellantisHorn(
            hass,
            data.coordinator,
            vehicle_data,
            entry,
        )
        for vehicle_data in data.coordinator.vehicles_data
    )


class StellantisHorn(StellantisBaseToggleEntity, SirenEntity):
    """Representation of Stellantis vehicle horn."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: StellantisUpdateCoordinator,
        vehicle: VehicleData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the vehicle horn."""
        super().__init__(
            hass,
            coordinator,
            vehicle,
            SirenEntityDescription(
                key="horn",
                translation_key="horn",
            ),
            entry,
            None,
            {"horn": {"state": "Activated"}},
            {"horn": {"state": "Unactivated"}},
            "activate the horn",
            "deactivate the horn",
        )
        self._attr_supported_features = (
            SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
        )

    def on_remote_action_success(self, state_if_success) -> None:
        """Handle the success of the remote action.

        Because we cannot get the status of the horn, we don't assume the state.
        """
