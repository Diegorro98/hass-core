"""Test the Stellantis config flow."""

from unittest.mock import patch

import pycountry

from homeassistant import config_entries
from homeassistant.components.stellantis.const import (
    API_ENDPOINT,
    CONF_BRAND,
    DOMAIN,
    Brand,
)
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
            CONF_BRAND: Brand.PEUGEOT,
            CONF_COUNTRY: pycountry.countries.get(alpha_2="ES").alpha_2,
        },
    )
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
    expected_token_request_data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
    }
    aioclient_mock.get(
        API_ENDPOINT + "/user",
        params={"client_id": "1eebc2d5-5df3-459b-a624-20abfcf82530"},
        json={
            "email": "example@domain.com",
        },
    )
    with (
        patch(
            "homeassistant.components.stellantis.oauth.StellantisOauth2Implementation._token_request",
            return_value={
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
        ) as token_request_mock,
        patch(
            "homeassistant.components.stellantis.async_setup_entry", return_value=True
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: f"https://example.com/auth?code={auth_code}&state={state}",
            },
        )
    token_request_mock.assert_called_once_with(expected_token_request_data)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_setup.call_count == 1


async def test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check reauth flow."""

    result = await hass.config_entries.flow.async_init(
        "stellantis",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_COUNTRY: pycountry.countries.get(alpha_2="ES").alpha_2,
        },
    )
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
    expected_token_request_data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
    }
    aioclient_mock.get(
        API_ENDPOINT + "/user",
        params={"client_id": "1eebc2d5-5df3-459b-a624-20abfcf82530"},
        json={
            "email": "example@domain.com",
        },
    )
    with (
        patch(
            "homeassistant.components.stellantis.oauth.StellantisOauth2Implementation._token_request",
            return_value={
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
        ) as token_request_mock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: f"https://example.com/auth?code={auth_code}&state={state}",
            },
        )
    token_request_mock.assert_called_once_with(expected_token_request_data)

    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
