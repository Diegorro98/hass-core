"""API for Stellantis."""

from asyncio import timeout
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Self

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientResponseError

from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER
from .oauth import StellantisOAuth2Session


@dataclass(frozen=True)
class VehicleData:
    """Vehicle Data."""

    vin: str
    id: str
    brand: str | None
    label: str | None

    @classmethod
    def parse_from_api_data(cls, vehicle_raw_data: dict[str, Any]) -> Self:
        """Parse vehicle data from the API."""
        branding: dict[str, str] = vehicle_raw_data["_embedded"]["extension"][
            "branding"
        ]
        return cls(
            vehicle_raw_data["vin"],
            vehicle_raw_data["id"],
            branding.get("brand"),
            branding.get("label"),
        )


class StellantisApi:
    """API class for Stellantis."""

    def __init__(self, session: StellantisOAuth2Session) -> None:
        """Initialize the API class."""
        self.session = session

    async def async_get_vehicles(self) -> list[VehicleData] | None:
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
                response = await self.session.async_request_to_path(
                    "GET",
                    "/user/vehicles",
                    params=params,
                )

            response.raise_for_status()

            result = await response.json()
            vehicles = [
                VehicleData.parse_from_api_data(vehicle_data)
                for vehicle_data in result["_embedded"]["vehicles"]
            ]
            while "next" in result["_links"]:
                next_page = result["_links"]["next"]["href"]
                async with timeout(10):
                    response = await self.session.async_request(
                        "POST", next_page, params=params
                    )
                    response.raise_for_status()

                    result = await response.json()
                    vehicles += [
                        VehicleData.parse_from_api_data(vehicle_data)
                        for vehicle_data in result["_embedded"]["vehicles"]
                    ]

        except ClientResponseError as error:
            LOGGER.exception("Failed to get vehicles: %s (HTTP error code %s)", HTTPStatus(error.status).phrase, error.status)
        except (TimeoutError, ClientError, KeyError) as error:
            LOGGER.exception("Failed to get vehicles: %s", error)
        else:
            return vehicles

    async def async_get_vehicle_status(
        self, vehicle: VehicleData
    ) -> dict[str, Any] | None:
        """Get vehicle data."""
        async with timeout(10):
            response = await self.session.async_request_to_path(
                "GET",
                f"/user/vehicles/{vehicle.id}/status",
            )

        if response.status != HTTPStatus.OK:
            LOGGER.error("Failed to get vehicle status for %s", vehicle.vin)
            return None

        return await response.json()

    async def async_send_remote_action(
        self, vehicle: VehicleData, callback_id: str, request_body: dict[str, Any]
    ) -> dict[str, Any]:
        """Send remote action."""
        async with timeout(10):
            response = await self.session.async_request_to_path(
                "POST",
                f"/user/vehicles/{vehicle.id}/callbacks/{callback_id}/remotes",
                json={"label": "hass_remote_action", **request_body},
            )
        if response.status != HTTPStatus.ACCEPTED:
            LOGGER.debug(
                f"More info about the exception that is after this log:\n\tHTTP response code: {response.status}\n\tHTTP Response: {await response.text()}"
            )
            raise HomeAssistantError(
                f"Remote action not accepted (HTTP response code {response.status})"
            )
        return await response.json()
