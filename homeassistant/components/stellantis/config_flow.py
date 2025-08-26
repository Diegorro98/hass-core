"""Config flow for Stellantis integration."""

from collections.abc import Mapping
import logging
import secrets
from types import MappingProxyType
from typing import Any, cast

import aiohttp
import pycountry
from stellantis.client import Client as StellantisClient
from stellantis.model.error import StellantisError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_URL, CONF_WEBHOOK_ID
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    _decode_jwt,
)
from homeassistant.helpers.selector import CountrySelector, CountrySelectorConfig

from .api import AsyncConfigEntryAuth
from .const import CONF_BRAND, DOMAIN, Brand
from .oauth import StellantisOauth2Implementation, StellantisOAuth2Session


class StellantisConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Stellantis."""

    VERSION = 1
    DOMAIN = DOMAIN

    flow_impl: StellantisOauth2Implementation
    brand: str | None = None
    country_code: str | None = None

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
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"brand": self.init_data[CONF_BRAND]},
            )

        return await self.async_step_user(self.init_data)

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

        self.brand = cast(str, user_input[CONF_BRAND])
        self.country_code = cast(str, user_input[CONF_COUNTRY]).lower()

        self.flow_impl = StellantisOauth2Implementation(
            self.hass, DOMAIN, Brand(self.brand), self.country_code
        )
        oauth_url = await self.flow_impl.async_generate_authorize_url(self.flow_id)
        return self.async_show_form(
            step_id="login",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                }
            ),
            description_placeholders={
                "oauth_url": oauth_url,
                "brand": self.brand,
                "redirect_uri": self.flow_impl.redirect_uri + self.country_code,
            },
        )

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for the flow."""
        email = "Unknown email"
        try:
            dummy_entry = ConfigEntry(
                version=0,
                minor_version=0,
                discovery_keys=MappingProxyType({}),
                domain=DOMAIN,
                options=None,
                data=data,
                source="dummy",
                unique_id=None,
                subentries_data=None,
                title="dummy",
            )
            oauth_session = StellantisOAuth2Session(
                self.hass, dummy_entry, self.flow_impl
            )
            auth = AsyncConfigEntryAuth(self.hass, oauth_session)
            await auth.async_get_access_token()
            data.update(dummy_entry.data)

            stellantis_client = StellantisClient(auth)

            user = await stellantis_client.get_user()
            if user.email:
                email = user.email
        except (
            TimeoutError,
            aiohttp.ClientError,
            aiohttp.ClientResponseError,
            StellantisError,
        ):
            pass

        title = f"{self.brand}: {email}"
        data[CONF_BRAND] = self.brand
        data[CONF_COUNTRY] = self.country_code
        if self.init_data:
            data[CONF_WEBHOOK_ID] = self.init_data[CONF_WEBHOOK_ID]
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                title=title,
                data=data,
            )
        data[CONF_WEBHOOK_ID] = secrets.token_hex()
        return self.async_create_entry(title=title, data=data)
