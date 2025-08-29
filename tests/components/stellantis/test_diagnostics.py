"""Test diagnostics for Stellantis."""

from stellantis.model import Vehicle
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stellantis.const import DOMAIN
from homeassistant.components.stellantis.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await async_get_config_entry_diagnostics(hass, config_entry) == snapshot


async def test_async_get_device_diagnostics_vehicle(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: Vehicle,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device config entry diagnostics."""
    assert vehicle_details.vin
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    assert await async_get_device_diagnostics(hass, config_entry, device) == snapshot


async def test_async_get_device_diagnostics_vehicle_without_embedded_extension(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    vehicle_details: Vehicle,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device config entry diagnostics from a vehicle whose details don't contain extension."""
    vehicle_details.embedded = None

    assert vehicle_details.vin
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, vehicle_details.vin)},
    )

    assert await async_get_device_diagnostics(hass, config_entry, device) == snapshot
