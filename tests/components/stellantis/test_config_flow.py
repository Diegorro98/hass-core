"""Test the Stellantis config flow."""

from unittest.mock import patch

import pytest
from stellantis.client import AbstractAuth, Client as StellantisClient
from stellantis.model import User
from stellantis.model.error import StellantisError
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.stellantis.const import CONF_BRAND, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_COUNTRY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_full_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        "stellantis",
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "brand_country"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BRAND: "Peugeot",
            CONF_COUNTRY: "ES",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "login"
    oauth_url = result["description_placeholders"]["oauth_url"]

    assert oauth_url.startswith("https://idpcvs.peugeot.com/am/oauth2/authorize")

    oauth_url = URL(oauth_url)
    redirect_uri = "mymap://oauth2redirect/es"
    assert oauth_url.query["redirect_uri"] == redirect_uri
    state = oauth_url.query["state"]
    assert oauth_url.query["response_type"] == "code"
    assert oauth_url.query["client_id"] == "1eebc2d5-5df3-459b-a624-20abfcf82530"
    assert oauth_url.query["scope"] == "openid profile"

    auth_code = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "authorization",
            "code": auth_code,
            "redirect_uri": redirect_uri,
        },
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch.object(
            StellantisClient, "get_user", return_value=User(email="example@domain.com")
        ) as client_get_user_mock,
        patch.object(
            StellantisClient, "__init__", return_value=None
        ) as mock_client_init,
        patch(
            "homeassistant.components.stellantis.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: f"https://example.com/auth?code={auth_code}&state={state}",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY

    client_get_user_mock.assert_called_once()

    # Find the entry by domain and get the first entry for the domain
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_called_once_with(hass, entry)

    abstract_auth_impl = mock_client_init.call_args[0][0]
    assert isinstance(abstract_auth_impl, AbstractAuth)
    assert await abstract_auth_impl.async_get_access_token() == "mock-access-token"


@pytest.mark.usefixtures("setup_integration")
async def test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check reauth flow."""
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "login"

    redirect_uri = "https://example.com/auth/external/callback"
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": redirect_uri,
        },
    )
    auth_code = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
        },
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with (
        patch.object(
            StellantisClient, "get_user", return_value=User(email="example@domain.com")
        ),
        patch(
            "homeassistant.components.stellantis.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: f"https://example.com/auth?code={auth_code}&state={state}",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED
    mock_setup_entry.assert_called_once_with(hass, entry)


async def test_flow_invalid_url_abort(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check that and invalid url does abort the flow."""
    result = await hass.config_entries.flow.async_init(
        "stellantis",
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BRAND: "Peugeot",
            CONF_COUNTRY: "ES",
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://example.com/auth",
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_url"


async def test_flow_get_user_error_abort(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check that an error while trying to obtain the user aborts the flow."""
    result = await hass.config_entries.flow.async_init(
        "stellantis",
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "brand_country"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BRAND: "Peugeot",
            CONF_COUNTRY: "ES",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "login"
    oauth_url = result["description_placeholders"]["oauth_url"]

    assert oauth_url.startswith("https://idpcvs.peugeot.com/am/oauth2/authorize")

    oauth_url = URL(oauth_url)
    redirect_uri = "mymap://oauth2redirect/es"
    assert oauth_url.query["redirect_uri"] == redirect_uri
    state = oauth_url.query["state"]
    assert oauth_url.query["response_type"] == "code"
    assert oauth_url.query["client_id"] == "1eebc2d5-5df3-459b-a624-20abfcf82530"
    assert oauth_url.query["scope"] == "openid profile"

    auth_code = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "authorization",
            "code": auth_code,
            "redirect_uri": redirect_uri,
        },
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch.object(
        StellantisClient, "get_user", side_effect=StellantisError("A test error")
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: f"https://example.com/auth?code={auth_code}&state={state}",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "get_user_error"
    assert result["description_placeholders"]["error"] == "A test error"


async def test_flow_get_user_missing_email(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check that if the user data returned by the API doesn't contain the email the flow is aborted."""
    result = await hass.config_entries.flow.async_init(
        "stellantis",
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "brand_country"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_BRAND: "Peugeot",
            CONF_COUNTRY: "ES",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "login"
    oauth_url = result["description_placeholders"]["oauth_url"]

    assert oauth_url.startswith("https://idpcvs.peugeot.com/am/oauth2/authorize")

    oauth_url = URL(oauth_url)
    redirect_uri = "mymap://oauth2redirect/es"
    assert oauth_url.query["redirect_uri"] == redirect_uri
    state = oauth_url.query["state"]
    assert oauth_url.query["response_type"] == "code"
    assert oauth_url.query["client_id"] == "1eebc2d5-5df3-459b-a624-20abfcf82530"
    assert oauth_url.query["scope"] == "openid profile"

    auth_code = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "authorization",
            "code": auth_code,
            "redirect_uri": redirect_uri,
        },
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch.object(StellantisClient, "get_user", return_value=User()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: f"https://example.com/auth?code={auth_code}&state={state}",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "missing_email"


@pytest.mark.usefixtures("setup_integration")
async def test_reauth_flow_different_id_abort(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check that reauthenticating with a different account aborts the flow."""
    different_email = "different@domain.com"
    assert config_entry.unique_id != different_email
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "login"

    redirect_uri = "https://example.com/auth/external/callback"
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": redirect_uri,
        },
    )
    auth_code = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

    aioclient_mock.post(
        "https://idpcvs.peugeot.com/am/oauth2/access_token",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
        },
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch.object(
        StellantisClient, "get_user", return_value=User(email=different_email)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: f"https://example.com/auth?code={auth_code}&state={state}",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
