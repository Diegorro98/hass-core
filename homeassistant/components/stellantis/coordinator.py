"""Data update coordinator for Stellantis API."""

from asyncio import timeout
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
from typing import Any, Literal

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API_ENDPOINT, DOMAIN, LOGGER
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session


@dataclass(frozen=True)
class VehicleData:
    """Vehicle Data."""

    vin: str
    id: str
    brand: str | None
    label: str | None

    @staticmethod
    def parse_from_api_data(vehicle_raw_data: dict[str, Any]):
        """Parse vehicle data from the API."""
        branding: dict[str, str] = vehicle_raw_data["_embedded"]["extension"][
            "branding"
        ]
        return VehicleData(
            vehicle_raw_data["vin"],
            vehicle_raw_data["id"],
            branding.get("brand"),
            branding.get("label"),
        )


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
        self.session = session
        self.vehicles_data: list[VehicleData] = []
        self.vehicles_status: dict[str, dict[str, Any]] = {}

    async def get_vehicles(self) -> bool | None:
        """Get vehicles."""
        params = {
            "extension": [
                # "onboardCapabilities", Causes HTTP 500 error
                "branding",
                "pictures",
            ],
        }
        try:
            async with timeout(10):
                response = await self.session.async_request(
                    "GET",
                    API_ENDPOINT + "/user/vehicles",
                    params=params,
                )

            if response.status != HTTPStatus.OK:
                return False

            result = await response.json()
            self.vehicles_data = [
                VehicleData.parse_from_api_data(vehicle_data)
                for vehicle_data in result["_embedded"]["vehicles"]
            ]
            while "next" in result["_links"]:
                next_page = result["_links"]["next"]["href"]
                async with timeout(10):
                    response = await self.session.async_request(
                        "POST", next_page, params=params
                    )
                    if response.status == HTTPStatus.OK:
                        result = await response.json()
                        self.vehicles_data += [
                            VehicleData.parse_from_api_data(vehicle_data)
                            for vehicle_data in result["_embedded"]["vehicles"]
                        ]
                    else:
                        break
        except (TimeoutError, ClientError):
            LOGGER.error("Failed to get vehicles")

    async def get_vehicle_status(self, vehicle: VehicleData) -> None:
        """Get vehicle data."""
        async with timeout(10):
            response = await self.session.async_request(
                "GET",
                f"{API_ENDPOINT}/user/vehicles/{vehicle.id}/status",
            )

        if response.status != HTTPStatus.OK:
            LOGGER.error("Failed to get vehicle status for %s", vehicle.vin)
            self.vehicles_status[vehicle.vin] = {}
            return

        self.vehicles_status[vehicle.vin] = await response.json()

    async def async_config_entry_first_refresh(self) -> None:
        """Fetch initial data."""
        await self.get_vehicles()
        await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Stellantis API."""
        for vehicle in self.vehicles_data:
            await self.get_vehicle_status(vehicle)

        return self.vehicles_status
