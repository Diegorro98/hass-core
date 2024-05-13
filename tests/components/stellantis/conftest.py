"""Tests for the Stellantis integration."""

import json
import time
from unittest.mock import patch

import pytest

from homeassistant.components.stellantis.api import VehicleDetails
from homeassistant.components.stellantis.const import (
    API_ENDPOINT,
    CONF_BRAND,
    CONF_CALLBACK_ID,
    DOMAIN,
    Brand,
)
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURE_VEHICLE_DETAILS = VehicleDetails(
    "TEST_VIN_00000000",
    "test_id",
    "Hybrid",
    Brand.PEUGEOT.value,
    "SUV 3008",
)
FIXTURE_CLIENT_ID = "1eebc2d5-5df3-459b-a624-20abfcf82530"


@pytest.fixture(name="config_entry")
async def setup_mocked_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> MockConfigEntry:
    """Mock a fully setup config entry and all components based on fixtures."""

    mock_callback_id = "mock-callback-id"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_WEBHOOK_ID: "mock-webhook-id",
            CONF_CALLBACK_ID: mock_callback_id,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_at": time.time() + 60,
            },
        },
    )
    entry.add_to_hass(hass)

    mock_instance_url = "http://example.nabu.casa"
    aioclient_mock.get(
        f"{API_ENDPOINT}/user/callbacks/{mock_callback_id}",
        params={"client_id": FIXTURE_CLIENT_ID},
        json={
            "subscribe": {
                "type": ["Remote"],
                "callback": {
                    "webhook": {
                        "target": mock_instance_url + "/api/webhook/mock-webhook-id",
                    }
                },
            }
        },
    )

    aioclient_mock.get(
        f"{API_ENDPOINT}/user/vehicles",
        params={"client_id": FIXTURE_CLIENT_ID},
        json={
            "_links": {},
            "_embedded": {
                "vehicles": [
                    {
                        "vin": FIXTURE_VEHICLE_DETAILS.vin,
                        "id": FIXTURE_VEHICLE_DETAILS.id,
                        "motorization": FIXTURE_VEHICLE_DETAILS.motorization,
                        "_embedded": {
                            "extension": {
                                "branding": {
                                    "brand": FIXTURE_VEHICLE_DETAILS.brand,
                                    "label": FIXTURE_VEHICLE_DETAILS.label,
                                }
                            }
                        },
                    },
                ]
            },
        },
    )

    aioclient_mock.get(
        f"{API_ENDPOINT}/user/vehicles/{FIXTURE_VEHICLE_DETAILS.id}/status",
        params={"client_id": FIXTURE_CLIENT_ID},
        json=json.loads(load_fixture("vehicle_status.json", "stellantis")),
    )

    with (
        patch(
            "homeassistant.components.stellantis.get_url",
            return_value=mock_instance_url,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="vehicle_details")
def vehicle_fixture() -> VehicleDetails:
    """Define a vehicle fixture."""
    return FIXTURE_VEHICLE_DETAILS
