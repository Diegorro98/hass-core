"""Test OAuth component for Stellantis component."""

from http import HTTPStatus
import time
from unittest.mock import MagicMock, patch

import pytest
from stellantis.model import Vehicle
from stellantis.model.error import StellantisApiError

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture
async def setup_integration() -> None:
    """Override the setup_integration fixture to avoid auto-using it."""


@pytest.fixture
async def setup_integration_override(
    hass: HomeAssistant,
    platforms: list[Platform],
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> bool:
    """Fixture to setup the integration."""
    config_entry.add_to_hass(hass)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    with (
        patch("homeassistant.components.stellantis.PLATFORMS", platforms),
        patch(
            "homeassistant.components.stellantis.StellantisClient", return_value=client
        ),
    ):
        return await hass.config_entries.async_setup(config_entry.entry_id)


async def test_expired_token(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test that the token is correctly refreshed when expired."""
    config_entry.data["token"]["expires_at"] = time.time() - 60
    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "refresh_token",
            "scope": "openid profile",
            "refresh_token": "mock-refresh-token",
        },
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.stellantis.StellantisClient", return_value=client
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("setup_integration_override")
async def test_revoked_token(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
) -> None:
    """Test that the ConfigEntryAuthFailed exception is raised when the token is revoked while coordinator is updating."""
    await async_setup_component(hass, HA_DOMAIN, {})
    assert config_entry.state is ConfigEntryState.LOADED

    client.get_vehicle_status.return_value = None
    client.get_vehicle_status.side_effect = StellantisApiError(HTTPStatus.UNAUTHORIZED)

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "sensor.peugeot_suv_3008_ignition"},
        blocking=True,
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id
