"""oAuth2 functions and classes for Stellantis API integration."""

from json import JSONDecodeError
import logging
from typing import cast

from aiohttp import BasicAuth, ClientError

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import Brand

_LOGGER = logging.getLogger(__name__)


class StellantisOauth2Implementation(AuthImplementation):
    """Local OAuth2 implementation for Stellantis."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        credential: ClientCredential,
        brand: Brand,
        country_code: str,
    ) -> None:
        """Stellantis Oauth Implementation."""
        match brand:
            case Brand.CITROEN:
                brand_tld = "citroen.com"
                self.realm = "clientsB2CCitroen"
                self.redirect_scheme = "mymacsdk"
            case Brand.DS:
                brand_tld = "driveds.com"
                self.realm = "clientsB2CDS"
                self.redirect_scheme = "mymdssdk"
            case Brand.OPEL:
                brand_tld = "opel.com"
                self.realm = "clientsB2COpel"
                self.redirect_scheme = "mymopsdk"
            case Brand.PEUGEOT:
                brand_tld = "peugeot.com"
                self.realm = "clientsB2CPeugeot"
                self.redirect_scheme = "mymap"
            case Brand.VAUXHALL:
                brand_tld = "vauxhall.co.uk"
                self.realm = "clientsB2CVauxhall"
                self.redirect_scheme = "mymvxsdk"
        super().__init__(
            hass=hass,
            auth_domain=domain,
            credential=credential,
            authorization_server=AuthorizationServer(
                authorize_url=f"https://idpcvs.{brand_tld}/am/oauth2/authorize",
                token_url=f"https://idpcvs.{brand_tld}/am/oauth2/access_token",
            ),
        )
        self.revoke_url = f"https://idpcvs.{brand_tld}/am/oauth2/token/revoke"
        self.country_code = country_code

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": "openid profile",
            "locale": f"{self.hass.config.language}-{self.country_code.upper()}",
        }

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return f"{self.redirect_scheme}://oauth2redirect/{self.country_code}"

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens."""
        return await self._token_request(
            {
                "grant_type": "refresh_token",
                "scope": "openid profile",
                "refresh_token": token["refresh_token"],
            }
        )

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        session = async_get_clientsession(self.hass)

        _LOGGER.debug("Sending token request to %s", self.token_url)
        resp = await session.post(
            self.token_url,
            params=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=BasicAuth(self.client_id, self.client_secret),
        )
        if resp.status >= 400:
            try:
                error_response = await resp.json()
            except (ClientError, JSONDecodeError):
                error_response = {}
            error_code = error_response.get("error", "unknown")
            error_description = error_response.get("error_description", "unknown error")
            _LOGGER.error(
                "Token request for %s failed (%s): %s",
                self.domain,
                error_code,
                error_description,
            )
        resp.raise_for_status()
        return cast(dict, await resp.json())

    async def async_revoke_token(self, token: dict) -> None:
        """Revoke a token."""
        session = async_get_clientsession(self.hass)
        await session.post(
            self.revoke_url,
            params={
                "token": token["refresh_token"],
                "realm": self.realm,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=BasicAuth(self.client_id, self.client_secret),
        )


class StellantisOAuth2Session(OAuth2Session):
    """OAuth2Session for Stellantis."""

    implementation: StellantisOauth2Implementation
