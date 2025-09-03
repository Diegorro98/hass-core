"""Data update coordinator for Stellantis API."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from typing import cast

from stellantis.client import Client as StellantisClient
from stellantis.model import Status, Vehicle
from stellantis.model.error import StellantisApiError, StellantisError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BRAND, DOMAIN, LOGGER

type StellantisConfigEntry = ConfigEntry[StellantisRuntimeData]


class StellantisRuntimeData:
    """Class to store Stellantis component runtime data."""

    def __init__(self, client: StellantisClient) -> None:
        """Initialize runtime data."""
        self.client = client
        self.vehicle_coordinators: list[StellantisVehicleCoordinator] = []
        self.callback_id: str | None = None


class StellantisVehicleCoordinator(DataUpdateCoordinator[Status]):
    """Data update coordinator for Stellantis API."""

    config_entry: StellantisConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: StellantisConfigEntry,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{config_entry.title.replace(': ', '_')}",
            update_interval=timedelta(seconds=60),
        )
        self.vehicle = vehicle

        brand = None
        label = None
        if (
            self.vehicle.embedded
            and self.vehicle.embedded.extension
            and self.vehicle.embedded.extension.branding
        ):
            brand = self.vehicle.embedded.extension.branding.brand
            label = self.vehicle.embedded.extension.branding.label
        if brand is None:
            brand = cast(str, config_entry.data[CONF_BRAND])

        assert self.vehicle.id is not None
        assert self.vehicle.vin
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, self.vehicle.vin)},
            manufacturer=brand,
            model=label,
            hw_version=self.vehicle.motorization,
            name=f"{brand} {label or ''}",
            serial_number=self.vehicle.vin,
        )

    async def _async_update_data(self) -> Status:
        """Fetch data from Stellantis API."""
        assert self.vehicle.id is not None
        try:
            self.data = await self.config_entry.runtime_data.client.get_vehicle_status(
                self.vehicle.id
            )
        except StellantisError as err:
            if isinstance(err, StellantisApiError):
                if err.code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    raise ConfigEntryAuthFailed from err
            raise UpdateFailed from err
        return self.data
