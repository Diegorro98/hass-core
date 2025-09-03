"""API for Home Connect bound to HASS OAuth."""

from typing import cast

from stellantis.client import AbstractAuth
from stellantis.const import API_ENDPOINT

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .oauth import StellantisOAuth2Session


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Stellantis authentication tied to an OAuth2 based config entry."""

    def __init__(
        self, hass: HomeAssistant, oauth_session: StellantisOAuth2Session
    ) -> None:
        """Initialize Stellantis Auth."""
        self.hass = hass
        super().__init__(
            get_async_client(hass),
            API_ENDPOINT,
            oauth_session.implementation.client_id,
            oauth_session.implementation.realm,
        )
        self.session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self.session.async_ensure_token_valid()

        return cast(str, self.session.token["access_token"])


class OneShotAuth(AbstractAuth):
    """Provide Stellantis authentication tied to an OAuth2 based config entry."""

    def __init__(
        self, hass: HomeAssistant, access_token: str, client_id: str, realm: str
    ) -> None:
        """Initialize Stellantis one shot auth."""
        self.access_token = access_token
        super().__init__(
            get_async_client(hass),
            API_ENDPOINT,
            client_id,
            realm,
        )

    async def async_get_access_token(self) -> str:
        """Return a valid access access token."""
        return self.access_token
