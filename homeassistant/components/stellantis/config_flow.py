"""Config flow for Stellantis integration."""

from collections.abc import Mapping
import logging
import secrets
from typing import Any, cast

import pycountry
from stellantis.client import AbstractAuth, Client as StellantisClient
from stellantis.const import API_ENDPOINT
from stellantis.model.error import StellantisError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_URL, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    _decode_jwt,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import CountrySelector, CountrySelectorConfig

from .const import CONF_BRAND, DOMAIN, Brand
from .oauth import StellantisOauth2Implementation


class _OneShotAuth(AbstractAuth):
    """Provide Stellantis authentication tied to an OAuth2 based config entry."""

    def __init__(
        self, hass: HomeAssistant, token: str, client_id: str, realm: str
    ) -> None:
        """Initialize Stellantis one shot auth."""
        self.token = token
        super().__init__(
            get_async_client(hass),
            API_ENDPOINT,
            client_id,
            realm,
        )

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self.token


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

            if not (code := url.query.get("code")) or not (
                raw_state := url.query.get("state")
            ):
                return self.async_abort(reason="invalid_url")
            self.external_data = {
                "code": code,
                "state": _decode_jwt(self.hass, raw_state),
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
        stellantis_client = StellantisClient(
            _OneShotAuth(
                self.hass,
                data["token"]["access_token"],
                self.flow_impl.client_id,
                self.flow_impl.realm,
            )
        )
        try:
            user = await stellantis_client.get_user()
        except StellantisError as err:
            return self.async_abort(
                reason="get_user_error", description_placeholders={"error": str(err)}
            )

        if user.email:
            email = user.email
        else:
            return self.async_abort(reason="missing_email")

        await self.async_set_unique_id(email)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data
            )
        self._abort_if_unique_id_configured()

        data.update(
            {
                CONF_BRAND: self.brand,
                CONF_COUNTRY: self.country_code,
                CONF_WEBHOOK_ID: secrets.token_hex(),
            }
        )
        return self.async_create_entry(title=f"{self.brand}: {email}", data=data)
