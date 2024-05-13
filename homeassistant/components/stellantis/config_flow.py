"""Config flow for Stellantis integration."""

from asyncio import timeout
from collections.abc import Mapping
from http import HTTPStatus
import logging
import secrets
from typing import Any

import aiohttp
import pycountry
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_URL, CONF_WEBHOOK_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    _decode_jwt,
)
from homeassistant.helpers.selector import CountrySelector, CountrySelectorConfig

from .const import API_ENDPOINT, CONF_BRAND, DOMAIN, Brand
from .oauth import StellantisOauth2Implementation


class StellantisConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Stellantis."""

    VERSION = 1
    DOMAIN = DOMAIN

    flow_impl: StellantisOauth2Implementation
    brand: Brand | None = None
    country_code: str | None = None
    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    def get_countries_config(self) -> CountrySelector:
        """Return the country selector config."""
        countries = [x.alpha_2 for x in pycountry.countries]
        return CountrySelector(
            CountrySelectorConfig(
                countries=list(countries),
            )
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_brand_country(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self.reauth_entry is None:
            raise HomeAssistantError("Reauth requested for non-existing entry")
        self.brand = Brand(self.reauth_entry.data[CONF_BRAND])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if self.brand is None:
            return self.async_abort(reason="no_brand_selected")
        if user_input is None or CONF_COUNTRY not in user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_COUNTRY, default=self.hass.config.country
                        ): await self.hass.async_add_executor_job(
                            self.get_countries_config
                        ),
                    }
                ),
                description_placeholders={
                    "brand": self.brand.value,
                },
            )
        return await self.async_step_login(user_input)

    async def async_step_brand_country(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if (
            user_input is not None
            and CONF_BRAND in user_input
            and CONF_COUNTRY in user_input
        ):
            return await self.async_step_login(user_input)

        return self.async_show_form(
            step_id="brand_country",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BRAND): vol.In(list(Brand)),
                    vol.Required(
                        CONF_COUNTRY, default=self.hass.config.country
                    ): await self.hass.async_add_executor_job(
                        self.get_countries_config
                    ),
                }
            ),
        )

    async def async_step_login(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle the login step."""

        if user_input is None:
            return self.async_abort(reason="no_user_input")

        if self.brand is None:
            if CONF_BRAND not in user_input:
                return self.async_abort(reason="no_brand_selected")

            if user_input[CONF_BRAND] not in list(Brand):
                return self.async_abort(reason="invalid_brand_selected")

            self.brand = Brand(user_input[CONF_BRAND])

        if CONF_URL in user_input:
            url = URL(user_input[CONF_URL])

            if "code" not in url.query or len(url.query["code"]) != 36:
                return self.async_abort(reason="invalid_url")

            state = _decode_jwt(self.hass, url.query["state"])

            self.external_data = {
                "code": url.query["code"],
                "state": state,
            }
            return await self.async_step_creation()

        if self.country_code is None:
            if CONF_COUNTRY not in user_input:
                return self.async_abort(reason="no_country_code_selected")

            self.country_code = user_input[CONF_COUNTRY].lower()

        self.flow_impl = StellantisOauth2Implementation(self.hass, DOMAIN, self.brand)
        oauth_url = await self.flow_impl.async_generate_authorize_url_with_country_code(
            self.flow_id, self.country_code
        )
        return self.async_show_form(
            step_id="login",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                }
            ),
            description_placeholders={
                "oauth_url": oauth_url,
                "brand": self.brand.value,
                "redirect_uri": self.flow_impl.redirect_uri + self.country_code,
            },
        )

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for the flow."""
        email = "Unknown email"
        if self.brand is None:
            return self.async_abort(reason="no_brand_selected")
        try:
            session = async_get_clientsession(self.hass)
            async with timeout(10):
                response = await session.get(
                    API_ENDPOINT + "/user",
                    params={"client_id": self.flow_impl.client_id},
                    headers={
                        "authorization": "Bearer " + data["token"]["access_token"],
                        "x-introspect-realm": self.flow_impl.realm,
                    },
                )

                if response.status == HTTPStatus.OK:
                    email = (await response.json())["email"]
        except (TimeoutError, aiohttp.ClientError):
            pass

        title = f"{self.brand.value}: {email}"
        data[CONF_BRAND] = self.brand.value
        if self.reauth_entry:
            data[CONF_WEBHOOK_ID] = self.reauth_entry.data[CONF_WEBHOOK_ID]
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                title=title,
                data=data,
            )
        data[CONF_WEBHOOK_ID] = secrets.token_hex()
        return self.async_create_entry(title=title, data=data)
