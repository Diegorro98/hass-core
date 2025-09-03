"""Diagnostics support for Stellantis."""

from dataclasses import asdict
from typing import Any

from stellantis.model import OnboardCapabilities, VehicleBranding

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import StellantisConfigEntry, StellantisVehicleCoordinator


async def _generate_appliance_diagnostics(
    vehicle_coordinator: StellantisVehicleCoordinator,
) -> dict[str, Any]:
    branding = VehicleBranding()
    onboard_capabilities = OnboardCapabilities()
    if vehicle_coordinator.vehicle.embedded and (
        vehicle_extension := vehicle_coordinator.vehicle.embedded.extension
    ):
        branding = vehicle_extension.branding or branding
        onboard_capabilities = (
            vehicle_extension.onboard_capabilities or onboard_capabilities
        )
    return {
        "id": vehicle_coordinator.vehicle.id,
        "vin": vehicle_coordinator.vehicle.vin,
        "motorization": vehicle_coordinator.vehicle.motorization,
        **asdict(branding),
        "onboard_capabilities": onboard_capabilities.to_dict(),
        "status": {
            k: v for k, v in vehicle_coordinator.data.to_dict().items() if k != "_links"
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: StellantisConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        vehicle_coordinator.vehicle.vin: await _generate_appliance_diagnostics(
            vehicle_coordinator
        )
        for vehicle_coordinator in entry.runtime_data.vehicle_coordinators
        if vehicle_coordinator.vehicle.vin is not None
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: StellantisConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    device_vin = next(
        (identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN),
    )
    vehicle_coordinator: StellantisVehicleCoordinator | None = None
    for _vehicle_coordinator in config_entry.runtime_data.vehicle_coordinators:
        if _vehicle_coordinator.vehicle.vin == device_vin:
            vehicle_coordinator = _vehicle_coordinator
            break
    assert vehicle_coordinator
    return await _generate_appliance_diagnostics(vehicle_coordinator)
