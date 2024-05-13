"""Test OAuth component for Stellantis component."""

from http import HTTPStatus
import time
from typing import cast

import pytest

from homeassistant.components.stellantis import HomeAssistantStellantisData
from homeassistant.components.stellantis.api import VehicleDetails
from homeassistant.components.stellantis.const import API_ENDPOINT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .conftest import FIXTURE_CLIENT_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

TOKEN_URL = "https://idpcvs.peugeot.com/am/oauth2/access_token"


async def test_expired_token(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the token is correctly refreshed when expired."""
    aioclient_mock.post(
        TOKEN_URL,
        params={
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

    assert hass.data[config_entry.domain][config_entry.entry_id]
    data = hass.data[config_entry.domain][config_entry.entry_id]
    assert isinstance(data, HomeAssistantStellantisData)
    data = cast(HomeAssistantStellantisData, data)

    data.session.token["expires_at"] = time.time() - 60
    assert not data.session.valid_token

    await data.session.async_ensure_token_valid()
    await hass.async_block_till_done()
    assert data.session.valid_token


async def test_revoked_token(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the ConfigEntryAuthFailed exception is raised when the token is revoked."""
    aioclient_mock.post(
        TOKEN_URL,
        params={
            "grant_type": "refresh_token",
            "scope": "openid profile",
            "refresh_token": "mock-refresh-token",
        },
        status=HTTPStatus.UNAUTHORIZED,
        json={},
    )

    assert hass.data[config_entry.domain][config_entry.entry_id]
    data = hass.data[config_entry.domain][config_entry.entry_id]
    assert isinstance(data, HomeAssistantStellantisData)
    data = cast(HomeAssistantStellantisData, data)

    data.session.token["expires_at"] = time.time() - 60
    assert not data.session.valid_token

    with pytest.raises(ConfigEntryAuthFailed):
        await data.session.async_ensure_token_valid()

    await hass.async_block_till_done()


async def test_revoked_token_while_refreshing(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    vehicle_details: VehicleDetails,
) -> None:
    """Test that the ConfigEntryAuthFailed exception is raised when the token is revoked while coordinator is updating."""

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{API_ENDPOINT}/user/vehicles/{vehicle_details.id}/status",
        params={"client_id": FIXTURE_CLIENT_ID},
        status=HTTPStatus.UNAUTHORIZED,
        json={},
    )

    assert hass.data[config_entry.domain][config_entry.entry_id]
    data = hass.data[config_entry.domain][config_entry.entry_id]
    assert isinstance(data, HomeAssistantStellantisData)
    data = cast(HomeAssistantStellantisData, data)

    assert data.session.valid_token

    with pytest.raises(ConfigEntryAuthFailed):
        await data.coordinator._async_update_data()

    await hass.async_block_till_done()
