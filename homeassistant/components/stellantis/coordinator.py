"""Data update coordinator for Stellantis API."""

from __future__ import annotations

from http import HTTPStatus
from typing import cast

from stellantis.client import Client as StellantisClient
from stellantis.model import Status, Vehicle, VehicleExtensionType
from stellantis.model.error import StellantisApiError, StellantisError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BRAND, DOMAIN, LOGGER, UPDATE_INTERVAL, VEHICLES_UPDATE_INTERVAL

type StellantisConfigEntry = ConfigEntry[StellantisRuntimeData]


class StellantisRuntimeData:
    """Class to store Stellantis component runtime data."""

    def __init__(
        self, client: StellantisClient, coordinator: StellantisCoordinator
    ) -> None:
        """Initialize runtime data."""
        self.client = client
        self.coordinator = coordinator
        self.callback_id: str | None = None


class StellantisCoordinator(
    DataUpdateCoordinator[dict[str, "StellantisVehicleCoordinator"]]
):
    """Data update coordinator for Stellantis vehicles."""

    config_entry: StellantisConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: StellantisConfigEntry,
    ) -> None:
        """Initialize the vehicles coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{config_entry.title.replace(': ', '_')}",
            update_interval=VEHICLES_UPDATE_INTERVAL,
        )
        self.data = {}

    async def _async_update_data(self) -> dict[str, StellantisVehicleCoordinator]:
        coordinators: dict[str, StellantisVehicleCoordinator] = self.data
        for attempt, extension in enumerate(
            (
                [
                    VehicleExtensionType.BRANDING,
                    VehicleExtensionType.ONBOARD_CAPABILITIES,
                ],
                [VehicleExtensionType.BRANDING],
            )
        ):
            try:
                vehicles_response = (
                    await self.config_entry.runtime_data.client.get_vehicles_by_device(
                        extension=extension
                    )
                )
            except StellantisError as err:
                if isinstance(err, StellantisApiError):
                    if err.code in (401, 403):
                        raise ConfigEntryAuthFailed from err
                    if err.code == 50055 and attempt == 0:
                        # Retry without ONBOARD_CAPABILITIES extension
                        continue
                raise ConfigEntryError from err

        coordinators_to_remove = set(coordinators.keys())
        if vehicles_response.embedded and (
            vehicles := vehicles_response.embedded.vehicles
        ):
            for vehicle in vehicles:
                if vehicle.vin is None:
                    continue
                if vehicle.vin in coordinators:
                    coordinators_to_remove.discard(vehicle.vin)
                    continue
                coordinator = StellantisVehicleCoordinator(
                    self.hass, self.config_entry, vehicle
                )
                await coordinator.async_config_entry_first_refresh()
                coordinators[vehicle.vin] = coordinator

        # Clean up vehicles which are not assigned to the account anymore
        for vin in coordinators_to_remove:
            coordinator = coordinators.pop(vin)
            await coordinator.async_shutdown()

        vehicles_identifiers = {(DOMAIN, vin) for vin in coordinators}
        device_registry = dr.async_get(self.hass)
        device_entries = dr.async_entries_for_config_entry(
            device_registry, config_entry_id=self.config_entry.entry_id
        )

        for device in device_entries:
            if not device.identifiers.intersection(vehicles_identifiers):
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )
        return coordinators


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
            name=f"{DOMAIN}-{config_entry.title.replace(': ', '_')}-{vehicle.vin}",
            update_interval=UPDATE_INTERVAL,
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
                if err.code == HTTPStatus.NOT_FOUND:
                    # Vehicle is no longer assigned to the account
                    await self.async_shutdown()
                    assert self.vehicle.vin
                    self.config_entry.runtime_data.coordinator.data.pop(
                        self.vehicle.vin, None
                    )
                    self.config_entry.runtime_data.coordinator.async_update_listeners()
                    device_registry = dr.async_get(self.hass)
                    device_entry = device_registry.async_get_device(
                        {(DOMAIN, self.vehicle.vin)},
                    )
                    if device_entry:
                        device_registry.async_update_device(
                            device_entry.id,
                            remove_config_entry_id=self.config_entry.entry_id,
                        )
                    LOGGER.info(
                        "The vehicle with VIN %s is no longer assigned to the account and has been removed",
                        self.vehicle.vin,
                    )
                    return self.data
            raise UpdateFailed from err
        return self.data
