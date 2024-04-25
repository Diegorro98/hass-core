"""Data update coordinator for Stellantis API."""

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import StellantisApi, VehicleData
from .const import DOMAIN, LOGGER
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session


class StellantisUpdateCoordinator(DataUpdateCoordinator):
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
        self.vehicles_data: list[VehicleData] = []
        self.vehicles_status: dict[str, dict[str, Any]] = {}

    async def async_config_entry_first_refresh(self) -> None:
        """Fetch initial data."""
        vehicle_data = await self.api.async_get_vehicles()
        if vehicle_data is None:
            return
        self.vehicles_data = vehicle_data
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Stellantis API."""
        for vehicle in self.vehicles_data:
            vehicle_status = await self.api.async_get_vehicle_status(vehicle)
            if vehicle_status is not None:
                self.vehicles_status[vehicle.vin] = vehicle_status

        return self.vehicles_status
