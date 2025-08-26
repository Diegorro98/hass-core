"""Tests for the Stellantis integration."""

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stellantis.client import Client as StellantisClient
from stellantis.model import (
    Callback,
    CallbackStatus,
    CallbackSubscribe,
    CallbackType,
    Motorization,
    Status,
    UserCallback,
    Vehicle,
    VehicleBranding,
    VehicleEmbedded,
    VehicleExtension,
    Vehicles,
    VehiclesEmbedded,
    Webhook,
)

from homeassistant.components.stellantis.const import (
    CONF_BRAND,
    CONF_CALLBACK_ID,
    DOMAIN,
    Brand,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_COUNTRY, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
FAKE_REFRESH_TOKEN = "some-refresh-token"
FAKE_AUTH_IMPL = "conftest-imported-cred"

SERVER_ACCESS_TOKEN = {
    "refresh_token": "server-refresh-token",
    "access_token": "server-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


FIXTURE_VEHICLE_DETAILS = Vehicle(
    vin="TEST_VIN_00000000",
    id="test_id",
    motorization=Motorization.HYBRID,
    embedded=VehicleEmbedded(
        extension=VehicleExtension(
            branding=VehicleBranding(
                brand=Brand.PEUGEOT.value,
                label="SUV 3008",
            )
        )
    ),
    links={},
)
FIXTURE_VEHICLE_STATUS = Status.from_json(
    load_fixture("vehicle_status.json", "stellantis")
)


@pytest.fixture(name="token_expiration_time")
def mock_token_expiration_time() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 86400


@pytest.fixture(name="token_entry")
def mock_token_entry(token_expiration_time: float) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "refresh_token": FAKE_REFRESH_TOKEN,
        "access_token": FAKE_ACCESS_TOKEN,
        "type": "Bearer",
        "expires_at": token_expiration_time,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_COUNTRY: "ES",
            CONF_WEBHOOK_ID: "mock-webhook-id",
            CONF_CALLBACK_ID: "mock-callback-id",
            "token": token_entry,
        },
        unique_id="1234567890",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture
async def setup_integration(
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


@pytest.fixture(name="client")
def mock_client() -> MagicMock:
    """Fixture to mock Client from Stellantis."""

    mock = MagicMock(
        autospec=StellantisClient,
    )

    mock.get_user_remote_by_id = AsyncMock(
        return_value=UserCallback(
            id="a test callback id",
            status=CallbackStatus.RUNNING,
            subscribe=CallbackSubscribe(
                type=[CallbackType.REMOTE],
                callback=Callback(
                    webhook=Webhook(
                        target="/api/webhook/mock-webhook-id",
                        name="a test webhook",
                    )
                ),
            ),
            links={},
        )
    )

    mock.get_vehicles_by_device = AsyncMock(
        return_value=Vehicles(
            embedded=VehiclesEmbedded(vehicles=[FIXTURE_VEHICLE_DETAILS]),
            total=1,
            total_page=1,
            current_page=1,
            links={},
        )
    )

    mock.get_vehicle_status = AsyncMock(return_value=FIXTURE_VEHICLE_STATUS)
    mock.send_remote_to_vhl = AsyncMock()

    return mock


@pytest.fixture(name="vehicle_details")
def vehicle_fixture() -> Vehicle:
    """Define a vehicle fixture."""
    return FIXTURE_VEHICLE_DETAILS
