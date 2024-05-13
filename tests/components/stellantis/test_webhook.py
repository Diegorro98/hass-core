"""Test Stellantis webhook."""

from homeassistant.components.stellantis.const import (
    ATTR_EVENT_STATUS,
    ATTR_REMOTE_ACTION_ID,
    ATTR_REMOTE_EVENT,
)
from homeassistant.components.stellantis.webhook import StellantisCallbackEvent
from homeassistant.components.webhook import DOMAIN as WEBHOOK_DOMAIN
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import RESULT_SUCCESS

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_stellantis_webhook(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test that webhooks set the result of the callback event."""
    assert await async_setup_component(hass, WEBHOOK_DOMAIN, {})

    remote_action_id = "test_remote_action_id"
    client = await hass_client_no_auth()
    with (
        StellantisCallbackEvent(hass, remote_action_id) as callback_event,
    ):
        resp = await client.post(
            "/api/webhook/" + config_entry.data[CONF_WEBHOOK_ID],
            json={
                ATTR_REMOTE_EVENT: {
                    ATTR_REMOTE_ACTION_ID: remote_action_id,
                    ATTR_EVENT_STATUS: RESULT_SUCCESS,
                }
            },
        )

    assert resp.status == 200
    assert callback_event.done()
    assert callback_event.result() == RESULT_SUCCESS
