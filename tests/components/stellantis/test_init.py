"""Test the Stellantis integration init functionality."""

from collections.abc import Callable
from http import HTTPStatus
from time import time
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from stellantis.client import Client as StellantisClient
from stellantis.model import (
    CallbackSubscribe,
    CallbackType,
    Vehicle,
    VehicleExtensionType,
)
from stellantis.model.error import StellantisApiError, StellantisError

from homeassistant.components import cloud
from homeassistant.components.stellantis.const import (
    CONF_BRAND,
    CONF_CLOUDHOOK_URL,
    DOMAIN,
    Brand,
)
from homeassistant.components.webhook import DOMAIN as WEBHOOK_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_COUNTRY, CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_mock_cloud_connection_status
from tests.components.cloud import mock_cloud
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
async def setup_integration() -> None:
    """Override the setup_integration fixture to avoid auto-using it."""


async def _setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> bool:
    """Fixture to setup the integration."""

    config_entry.add_to_hass(hass)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    with (
        patch("homeassistant.components.stellantis.PLATFORMS", []),
        patch(
            "homeassistant.components.stellantis.StellantisClient", return_value=client
        ),
    ):
        return await hass.config_entries.async_setup(config_entry.entry_id)


async def test_entry_setup(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test entry setup."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await _setup_integration(hass, config_entry, client)
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("config_entry", "brand_tld"),
    [
        ({CONF_BRAND: brand}, brand_tld)
        for brand, brand_tld in zip(
            Brand.__members__.values(),
            ("citroen.com", "driveds.com", "opel.com", "peugeot.com", "vauxhall.co.uk"),
            strict=True,
        )
    ],
    indirect=["config_entry"],
)
async def test_token_refresh_on_expired_token(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    client: MagicMock,
    brand_tld: str,
) -> None:
    """Test that the token is correctly refreshed when expired."""
    config_entry.data["token"]["expires_at"] = time() - 60
    aioclient_mock.post(
        f"https://idpcvs.{brand_tld}/am/oauth2/access_token",
        data={
            "grant_type": "refresh_token",
            "scope": "openid profile",
            "refresh_token": "mock-refresh-token",
        },
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-refresed-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    assert await _setup_integration(hass, config_entry, client)

    assert config_entry.state is ConfigEntryState.LOADED
    assert aioclient_mock.call_count == 1
    assert config_entry.data["token"]["access_token"] == "mock-refresed-access-token"


@pytest.mark.parametrize(
    ("aioclient_mock_args", "expected_config_entry_state"),
    [
        (
            {
                "status": HTTPStatus.BAD_REQUEST,
                "json": {"error": "invalid_grant"},
            },
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            {
                "status": HTTPStatus.INTERNAL_SERVER_ERROR,
            },
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            {
                "exc": aiohttp.ClientError,
            },
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_token_refresh_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    client: MagicMock,
    config_entry: MockConfigEntry,
    aioclient_mock_args: dict[str, Any],
    expected_config_entry_state: ConfigEntryState,
) -> None:
    """Test where token is expired and the refresh attempt fails."""
    config_entry.data["token"]["expires_at"] = time() - 60

    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "refresh_token",
            "scope": "openid profile",
            "refresh_token": "mock-refresh-token",
        },
        **aioclient_mock_args,
    )

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not await _setup_integration(hass, config_entry, client)

    assert config_entry.state == expected_config_entry_state


@pytest.mark.parametrize(
    ("exception", "reason_match"),
    [
        (StellantisError("Test exception"), "Test exception"),
        (
            StellantisApiError(HTTPStatus.BAD_REQUEST, message="Bad Request"),
            "Bad Request",
        ),
        (
            StellantisApiError(HTTPStatus.UNAUTHORIZED, message="Unauthorized"),
            "Unauthorized",
        ),
        (StellantisApiError(HTTPStatus.FORBIDDEN, message="Forbidden"), "Forbidden"),
        (
            StellantisApiError(
                HTTPStatus.INTERNAL_SERVER_ERROR, message="Internal Server Error"
            ),
            "Internal Server Error",
        ),
    ],
)
async def test_setup_entry_get_vehicles_error(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    exception: StellantisError,
    reason_match: str,
) -> None:
    """Test the setup entry when the call to obtain the vehicles fails."""
    client.get_vehicles_by_device.return_value = None
    client.get_vehicles_by_device.side_effect = exception

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not await _setup_integration(hass, config_entry, client)

    assert config_entry.state == ConfigEntryState.SETUP_ERROR
    assert config_entry.reason
    assert reason_match in config_entry.reason


async def test_setup_entry_get_vehicles_on_boarding_capabilities_error(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the setup entry when the call to obtain the vehicles fails."""
    client.get_vehicles_by_device.side_effect = [
        StellantisApiError(50055),
        client.get_vehicles_by_device.return_value,
    ]
    client.get_vehicles_by_device.return_value = None

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert await _setup_integration(hass, config_entry, client)
    assert config_entry.state == ConfigEntryState.LOADED

    assert client.get_vehicles_by_device.call_count == 2
    call_args_list = client.get_vehicles_by_device.call_args_list
    assert call_args_list[0][1]["extension"] == [
        VehicleExtensionType.BRANDING,
        VehicleExtensionType.ONBOARD_CAPABILITIES,
    ]
    assert call_args_list[1][1]["extension"] == [VehicleExtensionType.BRANDING]


@pytest.mark.parametrize(
    ("exception", "config_entry_state"),
    [
        (StellantisError(), ConfigEntryState.SETUP_RETRY),
        (StellantisApiError(HTTPStatus.BAD_REQUEST), ConfigEntryState.SETUP_RETRY),
        (StellantisApiError(HTTPStatus.UNAUTHORIZED), ConfigEntryState.SETUP_ERROR),
        (StellantisApiError(HTTPStatus.FORBIDDEN), ConfigEntryState.SETUP_ERROR),
        (
            StellantisApiError(HTTPStatus.INTERNAL_SERVER_ERROR),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_first_refresh_error(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    exception: StellantisError,
    config_entry_state: ConfigEntryState,
) -> None:
    """Test the setup entry when the call to obtain the vehicles fails."""
    client.get_vehicle_status.return_value = None
    client.get_vehicle_status.side_effect = exception

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not await _setup_integration(hass, config_entry, client)

    assert config_entry.state == config_entry_state


async def test_device_cleanance(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the devices that are not provided any longer are cleaned."""
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "TO_DELETE")},
    )

    assert await _setup_integration(hass, config_entry, client)

    assert not device_registry.async_get(device_entry.id)


@pytest.mark.parametrize("delete_user_remote_side_effect", [[None], [StellantisError]])
async def test_entry_unload(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    delete_user_remote_side_effect: list[Any],
) -> None:
    """Test entry unload."""
    client.delete_user_remote.side_effect = delete_user_remote_side_effect
    hass.config.external_url = "https://example.com"
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(WEBHOOK_DOMAIN, {}).get(config_entry.data[CONF_WEBHOOK_ID])

    assert await _setup_integration(hass, config_entry, client)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.data.get(WEBHOOK_DOMAIN, {}).get(config_entry.data[CONF_WEBHOOK_ID])

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(WEBHOOK_DOMAIN, {}).get(config_entry.data[CONF_WEBHOOK_ID])
    assert client.delete_user_remote.awaited_once_with("mock-callback-id")


@pytest.mark.parametrize(
    ("config_entry", "brand_tld", "realm"),
    [
        ({CONF_BRAND: brand}, brand_tld, realm)
        for brand, brand_tld, realm in zip(
            Brand.__members__.values(),
            ("citroen.com", "driveds.com", "opel.com", "peugeot.com", "vauxhall.co.uk"),
            (
                "clientsB2CCitroen",
                "clientsB2CDriveds",
                "clientsB2COpel",
                "clientsB2CPeugeot",
                "clientsB2CVauxhall",
            ),
            strict=True,
        )
    ],
    indirect=["config_entry"],
)
async def test_entry_removal(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    brand_tld: str,
    realm: str,
) -> None:
    """Test entry removal."""
    aioclient_mock.post(
        f"https://idpcvs.{brand_tld}/am/oauth2/access_token",
        data={
            "grant_type": "refresh_token",
            "scope": "openid profile",
            "refresh_token": "mock-refresh-token",
        },
        json={
            "refresh_token": "mock-refreshed-refresh-token",
            "access_token": "mock-refresed-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )
    aioclient_mock.post(
        f"https://idpcvs.{brand_tld}/am/oauth2/token/revoke",
        data={
            "realm": realm,
            "token": "mock-refreshed-refresh-token",
        },
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.async_get_entry(config_entry.entry_id)

    await hass.config_entries.async_remove(config_entry.entry_id)

    assert hass.config_entries.async_get_entry(config_entry.entry_id) is None

    assert len(aioclient_mock.mock_calls) == 2
    assert aioclient_mock.mock_calls[0] != aioclient_mock.mock_calls[1]


async def test_entry_removal_refresh_token_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the entry is removed although having an error while refreshing the token."""
    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "refresh_token",
            "scope": "openid profile",
            "refresh_token": "mock-refresh-token",
        },
        status=HTTPStatus.UNAUTHORIZED,
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.async_get_entry(config_entry.entry_id)

    await hass.config_entries.async_remove(config_entry.entry_id)

    assert hass.config_entries.async_get_entry(config_entry.entry_id) is None

    assert len(aioclient_mock.mock_calls) == 1


async def test_entry_removal_client_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Test entry removal."""
    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "refresh_token",
            "scope": "openid profile",
            "refresh_token": "mock-refresh-token",
        },
        json={
            "refresh_token": "mock-refreshed-refresh-token",
            "access_token": "mock-refresed-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )
    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/token/revoke",
        data={
            "realm": "clientsB2CPeugeot",
            "token": "mock-refreshed-refresh-token",
        },
    )
    config_entry.add_to_hass(hass)
    assert hass.config_entries.async_get_entry(config_entry.entry_id)

    with patch.object(
        StellantisClient, "delete_user_remote", side_effect=StellantisError
    ):
        await hass.config_entries.async_remove(config_entry.entry_id)

    assert hass.config_entries.async_get_entry(config_entry.entry_id) is None

    assert len(aioclient_mock.mock_calls) == 2
    assert aioclient_mock.mock_calls[0] != aioclient_mock.mock_calls[1]


async def test_reusable_callback_created(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    client: MagicMock,
) -> None:
    """Test that a reusable callback is created."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_COUNTRY: "ES",
            "token": token_entry,
        },
        unique_id="example@domain.com",
    )
    hass.config.internal_url = "https://192.168.1.2"
    hass.config.external_url = "https://example.com"

    assert await _setup_integration(hass, config_entry, client)

    client.set_user_vehicle_remote.assert_awaited_once()
    subscribe_data = cast(
        CallbackSubscribe, client.set_user_vehicle_remote.call_args[0][0]
    )
    assert subscribe_data.type
    assert CallbackType.REMOTE in subscribe_data.type
    assert subscribe_data.callback.webhook
    assert subscribe_data.callback.webhook.target == (
        "https://example.com/api/webhook/" + config_entry.data[CONF_WEBHOOK_ID]
    )
    assert config_entry.runtime_data.callback_id == "mock-callback-id"
    assert CONF_WEBHOOK_ID in config_entry.data
    assert CONF_CLOUDHOOK_URL not in config_entry.data


async def test_reusable_callback_created_with_cloudhook(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    client: MagicMock,
) -> None:
    """Test that a reusable callback is created with cloudhook URL."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_COUNTRY: "ES",
            "token": token_entry,
        },
        unique_id="example@domain.com",
    )
    await mock_cloud(hass)
    await hass.async_block_till_done()
    hass.config.internal_url = "https://192.168.1.2"
    hass.config.external_url = "https://example.com"

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value="https://hooks.nabu.casa/ABCD",
        ) as fake_create_cloudhook,
    ):
        assert await _setup_integration(hass, config_entry, client)
        fake_create_cloudhook.assert_called_once_with(
            hass, config_entry.data[CONF_WEBHOOK_ID]
        )

    client.set_user_vehicle_remote.assert_awaited_once()
    subscribe_data = cast(
        CallbackSubscribe, client.set_user_vehicle_remote.call_args[0][0]
    )
    assert subscribe_data.type
    assert CallbackType.REMOTE in subscribe_data.type
    assert subscribe_data.callback.webhook
    assert subscribe_data.callback.webhook.target == "https://hooks.nabu.casa/ABCD"
    assert config_entry.runtime_data.callback_id == "mock-callback-id"
    assert config_entry.data[CONF_CLOUDHOOK_URL] == "https://hooks.nabu.casa/ABCD"
    assert CONF_WEBHOOK_ID in config_entry.data


async def test_reusable_callback_created_with_ext_url_but_cloud_later(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    client: MagicMock,
) -> None:
    """Test that a reusable callback is created with external URL but cloud URL later after activating connection."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_COUNTRY: "ES",
            "token": token_entry,
        },
        unique_id="example@domain.com",
    )
    await mock_cloud(hass)
    await hass.async_block_till_done()
    hass.config.internal_url = "https://192.168.1.2"
    hass.config.external_url = "https://example.com"

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=False),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
        ) as fake_create_cloudhook,
    ):
        assert await _setup_integration(hass, config_entry, client)
        fake_create_cloudhook.assert_not_called()

    client.set_user_vehicle_remote.assert_awaited_once()
    subscribe_data = cast(
        CallbackSubscribe, client.set_user_vehicle_remote.call_args[0][0]
    )
    assert subscribe_data.type
    assert CallbackType.REMOTE in subscribe_data.type
    assert subscribe_data.callback.webhook
    assert subscribe_data.callback.webhook.target == (
        "https://example.com/api/webhook/" + config_entry.data[CONF_WEBHOOK_ID]
    )
    assert config_entry.runtime_data.callback_id == "mock-callback-id"
    assert CONF_WEBHOOK_ID in config_entry.data
    assert CONF_CLOUDHOOK_URL not in config_entry.data

    client.set_user_vehicle_remote_by_id = AsyncMock(
        return_value=client.set_user_vehicle_remote.return_value
    )

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value="https://hooks.nabu.casa/ABCD",
        ) as fake_create_cloudhook,
    ):
        async_mock_cloud_connection_status(hass, True)
        fake_create_cloudhook.assert_called_once()

    client.set_user_vehicle_remote_by_id.assert_awaited_once()
    assert client.set_user_vehicle_remote_by_id.call_args[0][0] == "mock-callback-id"
    subscribe_data = cast(
        CallbackSubscribe, client.set_user_vehicle_remote_by_id.call_args[0][1]
    )
    assert subscribe_data.type
    assert CallbackType.REMOTE in subscribe_data.type
    assert subscribe_data.callback.webhook
    assert subscribe_data.callback.webhook.target == "https://hooks.nabu.casa/ABCD"
    assert config_entry.runtime_data.callback_id == "mock-callback-id"
    assert config_entry.data[CONF_CLOUDHOOK_URL] == "https://hooks.nabu.casa/ABCD"
    assert CONF_WEBHOOK_ID in config_entry.data


async def test_reusable_callback_created_with_cloud_but_with_ext_url_later(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    client: MagicMock,
) -> None:
    """Test that a reusable callback is created with cloudhook URL but with external URL later after activating connection."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_COUNTRY: "ES",
            "token": token_entry,
        },
        unique_id="example@domain.com",
    )
    await mock_cloud(hass)
    await hass.async_block_till_done()
    hass.config.internal_url = "https://192.168.1.2"
    hass.config.external_url = "https://example.com"

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value="https://hooks.nabu.casa/ABCD",
        ) as fake_create_cloudhook,
    ):
        assert await _setup_integration(hass, config_entry, client)
        fake_create_cloudhook.assert_called_once()

    client.set_user_vehicle_remote.assert_awaited_once()
    subscribe_data = cast(
        CallbackSubscribe, client.set_user_vehicle_remote.call_args[0][0]
    )
    assert subscribe_data.type
    assert CallbackType.REMOTE in subscribe_data.type
    assert subscribe_data.callback.webhook
    assert subscribe_data.callback.webhook.target == "https://hooks.nabu.casa/ABCD"
    assert config_entry.runtime_data.callback_id == "mock-callback-id"
    assert config_entry.data[CONF_CLOUDHOOK_URL] == "https://hooks.nabu.casa/ABCD"
    assert CONF_WEBHOOK_ID in config_entry.data

    client.set_user_vehicle_remote_by_id = AsyncMock(
        return_value=client.set_user_vehicle_remote.return_value
    )

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=False),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
        ) as fake_create_cloudhook,
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook",
        ) as fake_delete_cloudhook,
    ):
        async_mock_cloud_connection_status(hass, False)
        fake_create_cloudhook.assert_not_called()
        fake_delete_cloudhook.assert_called_once_with(
            hass, config_entry.data[CONF_WEBHOOK_ID]
        )

    client.set_user_vehicle_remote_by_id.assert_awaited_once()
    assert client.set_user_vehicle_remote_by_id.call_args[0][0] == "mock-callback-id"
    subscribe_data = cast(
        CallbackSubscribe, client.set_user_vehicle_remote_by_id.call_args[0][1]
    )
    assert subscribe_data.type
    assert CallbackType.REMOTE in subscribe_data.type
    assert subscribe_data.callback.webhook
    assert subscribe_data.callback.webhook.target == (
        "https://example.com/api/webhook/" + config_entry.data[CONF_WEBHOOK_ID]
    )
    assert config_entry.runtime_data.callback_id == "mock-callback-id"
    assert CONF_WEBHOOK_ID in config_entry.data
    assert CONF_CLOUDHOOK_URL not in config_entry.data


async def test_reusable_callback_is_not_created_if_no_external_url(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    client: MagicMock,
) -> None:
    """Test that a reusable callback is not created if the external URL is missing and cloud is not connected."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_COUNTRY: "ES",
            "token": token_entry,
        },
        unique_id="example@domain.com",
    )
    hass.config.internal_url = "https://192.168.1.2"

    assert await _setup_integration(hass, config_entry, client)
    client.set_user_vehicle_remote.assert_not_awaited()

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    client.set_user_vehicle_remote.assert_not_awaited()


async def test_cloudhook_not_recreated_if_already_created(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    client: MagicMock,
) -> None:
    """Test that a reusable callback is created."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_COUNTRY: "ES",
            CONF_WEBHOOK_ID: "mock-webhook-id",
            CONF_CLOUDHOOK_URL: "https://hooks.nabu.casa/ABCD",
            "token": token_entry,
        },
        unique_id="example@domain.com",
    )
    await mock_cloud(hass)
    await hass.async_block_till_done()

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
        ) as fake_create_cloudhook,
    ):
        assert await _setup_integration(hass, config_entry, client)
        fake_create_cloudhook.assert_not_called()

    client.set_user_vehicle_remote.assert_awaited_once()
    subscribe_data = cast(
        CallbackSubscribe, client.set_user_vehicle_remote.call_args[0][0]
    )
    assert subscribe_data.type
    assert CallbackType.REMOTE in subscribe_data.type
    assert subscribe_data.callback.webhook
    assert subscribe_data.callback.webhook.target == "https://hooks.nabu.casa/ABCD"


@pytest.mark.parametrize("delete_user_remote_side_effect", [[None], [StellantisError]])
async def test_unregister_webhook_and_delete_remote_on_stop(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: MagicMock,
    delete_user_remote_side_effect: list[None | Exception],
) -> None:
    """Test that the webhook is unregistered and the remote is deleted on stop."""
    hass.config.internal_url = "https://192.168.1.2"
    hass.config.external_url = "https://example.com"
    client.delete_user_remote.side_effect = delete_user_remote_side_effect

    assert await _setup_integration(hass, config_entry, client)
    assert hass.data.get(WEBHOOK_DOMAIN, {}).get(config_entry.data[CONF_WEBHOOK_ID])

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    client.delete_user_remote.assert_awaited_once()
    client.delete_user_remote.assert_awaited_once_with("mock-callback-id")
    assert not hass.data.get(WEBHOOK_DOMAIN, {}).get(config_entry.data[CONF_WEBHOOK_ID])


async def tests_error_on_creating_remote(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test that an error is raised when creating a remote."""
    client.set_user_vehicle_remote.side_effect = StellantisError

    assert await _setup_integration(hass, config_entry, client)

    assert config_entry.runtime_data.callback_id is None


async def test_error_on_updating_remote(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test that an error is raised when updating a remote."""
    client.set_user_vehicle_remote_by_id.side_effect = StellantisError

    await mock_cloud(hass)
    await hass.async_block_till_done()
    hass.config.internal_url = "https://192.168.1.2"
    hass.config.external_url = "https://example.com"

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=False),
        patch("homeassistant.components.cloud.async_create_cloudhook"),
    ):
        assert await _setup_integration(hass, config_entry, client)

    assert config_entry.runtime_data.callback_id is not None

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch.object(cloud, "async_active_subscription", return_value=True),
        patch.object(cloud, "async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_create_cloudhook",
            return_value="https://hooks.nabu.casa/ABCD",
        ),
    ):
        async_mock_cloud_connection_status(hass, True)

    assert config_entry.runtime_data.callback_id is None


@pytest.mark.parametrize(
    "config_entry",
    [{CONF_BRAND: brand} for brand in Brand.__members__.values()],
    indirect=True,
)
@pytest.mark.parametrize(
    "vehicle_details_modification_function",
    [
        lambda vehicle_details: setattr(
            vehicle_details.embedded.extension.branding, "brand", None
        ),
        lambda vehicle_details: setattr(vehicle_details, "embedded", None),
    ],
)
async def test_conf_brand_in_device_if_not_provided(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    client: MagicMock,
    vehicle_details: Vehicle,
    vehicle_details_modification_function: Callable[[Vehicle], None],
) -> None:
    """Test that if the API does not provide the brand, the device manufacturer is the same than the config entry brand."""
    vehicle_details_modification_function(vehicle_details)

    await _setup_integration(hass, config_entry, client)

    assert vehicle_details.vin
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, vehicle_details.vin)}
    )
    assert device
    assert device.manufacturer == config_entry.data[CONF_BRAND]
