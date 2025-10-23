"""Application credentials platform for Stellantis."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return dummy authorization server.

    As it will be set depending on the entry configuration
    """
    return AuthorizationServer(
        authorize_url="",
        token_url="",
    )
