"""Data update coordinator for Stellantis API."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import StellantisApi, StellantisVehicle
from .const import DOMAIN, LOGGER
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session


class StellantisUpdateCoordinator(DataUpdateCoordinator[list[StellantisVehicle]]):
    """Data update coordinator for Stellantis API."""

    def __init__(
        self,
        hass: HomeAssistant,
        implementation: StellantisOauth2Implementation,
        session: StellantisOAuth2Session,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}-{entry.title.replace(': ', '_')}",
            update_interval=timedelta(seconds=60),
        )
        self.implementation = implementation
        self.api = StellantisApi(session)

    async def async_config_entry_first_refresh(self) -> None:
        """Fetch initial data."""
        vehicle_details = await self.api.async_get_vehicles_details()
        if vehicle_details is None:
            return
        self.data = [
            StellantisVehicle(vehicle_details) for vehicle_details in vehicle_details
        ]
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> list[StellantisVehicle]:
        """Fetch data from Stellantis API."""

        for vehicle in self.data:
            vehicle_status = await self.api.async_get_vehicle_status(vehicle)
            if vehicle_status is not None:
                vehicle.status = vehicle_status

        return self.data
