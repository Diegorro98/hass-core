"""oAuth2 functions and classes for Stellantis API integration."""

from http import HTTPStatus
from typing import Any, cast

from aiohttp import BasicAuth, client
from yarl import URL

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session, _encode_jwt

from .const import API_ENDPOINT, Brand


class StellantisOauth2Implementation(AuthImplementation):
    """Local OAuth2 implementation for Stellantis."""

    def __init__(self, hass: HomeAssistant, domain: str, brand: Brand) -> None:
        """Stellantis Oauth Implementation."""
        match brand:
            case Brand.CITROEN:
                client_credential = ClientCredential(
                    "5364defc-80e6-447b-bec6-4af8d1542cae",
                    "iE0cD8bB0yJ0dS6rO3nN1hI2wU7uA5xR4gP7lD6vM0oH0nS8dN",
                    brand.value,
                )
                brand_tld = "citroen.com"
                self.realm = "clientsB2CCitroen"
                self.redirect_scheme = "mymacsdk"
            case Brand.DS:
                client_credential = ClientCredential(
                    "cbf74ee7-a303-4c3d-aba3-29f5994e2dfa",
                    "X6bE6yQ3tH1cG5oA6aW4fS6hK0cR0aK5yN2wE4hP8vL8oW5gU3",
                    brand.value,
                )
                brand_tld = "driveds.com"
                self.realm = "clientsB2CDS"
                self.redirect_scheme = "mymdssdk"
            case Brand.OPEL:
                client_credential = ClientCredential(
                    "07364655-93cb-4194-8158-6b035ac2c24c",
                    "F2kK7lC5kF5qN7tM0wT8kE3cW1dP0wC5pI6vC0sQ5iP5cN8cJ8",
                    brand.value,
                )
                brand_tld = "opel.com"
                self.realm = "clientsB2COpel"
                self.redirect_scheme = "mymopsdk"
            case Brand.PEUGEOT:
                client_credential = ClientCredential(
                    "1eebc2d5-5df3-459b-a624-20abfcf82530",
                    "T5tP7iS0cO8sC0lA2iE2aR7gK6uE5rF3lJ8pC3nO1pR7tL8vU1",
                    brand.value,
                )
                brand_tld = "peugeot.com"
                self.realm = "clientsB2CPeugeot"
                self.redirect_scheme = "mymap"
            case Brand.VAUXHALL:
                client_credential = ClientCredential(
                    "122f3511-4f74-4a0c-bcda-af2f3b2e3a65",
                    "N1iY3jO4jI1sF2yS6yJ3rG7xQ4kL4kK1dO3xT5uX6dF3kW8gI6",
                    brand.value,
                )
                brand_tld = "vauxhall.co.uk"
                self.realm = "clientsB2CVauxhall"
                self.redirect_scheme = "mymvxsdk"
            case _:
                raise ValueError(f"Invalid brand: {brand}")
        super().__init__(
            hass=hass,
            auth_domain=domain,
            credential=client_credential,
            authorization_server=AuthorizationServer(
                authorize_url=f"https://idpcvs.{brand_tld}/am/oauth2/authorize",
                token_url=f"https://idpcvs.{brand_tld}/am/oauth2/access_token",
            ),
        )
        self.revoke_url = f"https://idpcvs.{brand_tld}/am/oauth2/token/revoke"

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "openid profile"}

    @property
    def redirect_uri(self) -> str:
        """Return the redirect uri."""
        return f"{self.redirect_scheme}://oauth2redirect/"

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
        resp = await session.post(
            self.token_url,
            params=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=BasicAuth(self.client_id, self.client_secret),
        )
        json = await resp.json()
        if resp.status >= 400 and resp.status < 500:
            raise ConfigEntryAuthFailed(
                json.get("error_description", json.get("moreInformation", "Unknown"))
            )
        resp.raise_for_status()
        return cast(dict, json)

    async def async_generate_authorize_url_with_country_code(
        self, flow_id: str, country_code: str
    ) -> str:
        """Generate a url for the user to authorize."""
        redirect_uri = self.redirect_uri
        return str(
            URL(self.authorize_url)
            .with_query(
                {
                    "response_type": "code",
                    "client_id": self.client_id,
                    "scope": "openid profile",
                    "redirect_uri": redirect_uri + country_code,
                    "state": _encode_jwt(
                        self.hass,
                        {
                            "flow_id": flow_id,
                            "redirect_uri": redirect_uri + country_code,
                        },
                    ),
                    "locale": f"{self.hass.config.language}-{country_code.upper()}",
                }
            )
            .update_query(self.extra_authorize_data)
        )

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

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        implementation: StellantisOauth2Implementation,
    ) -> None:
        """Initialize Stellantis OAuth2 session."""
        super().__init__(hass, config_entry, implementation)

    async def async_request(
        self, method: str, url: str, **kwargs: Any
    ) -> client.ClientResponse:
        """Make a request to Stellantis api."""
        headers = kwargs.pop("headers", {})
        params = kwargs.pop("params", {})
        resp = await super().async_request(
            method,
            url,
            **kwargs,
            params={
                **params,
                "client_id": self.implementation.client_id,
            },
            headers={
                **headers,
                "x-introspect-realm": self.implementation.realm,
            },
        )
        if resp.status == HTTPStatus.UNAUTHORIZED and self.valid_token:
            json = await resp.json()
            raise ConfigEntryAuthFailed(
                json.get("error_description", json.get("moreInformation", "Unknown"))
            )
        return resp

    async def async_request_to_path(
        self, method: str, path: str, **kwargs: Any
    ) -> client.ClientResponse:
        """Make a request to Stellantis api endpoint and the given path."""
        return await self.async_request(
            method,
            API_ENDPOINT + path,
            **kwargs,
        )

    async def async_revoke_token(self) -> None:
        """Revoke the token."""
        await self.implementation.async_revoke_token(self.token)

        self.hass.config_entries.async_update_entry(
            self.config_entry, data={**self.config_entry.data, "token": None}
        )
