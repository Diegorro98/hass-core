"""Test Stellantis webhook."""

import pytest
from stellantis.model import Message, RemoteEvent

from homeassistant.components.stellantis.webhook import StellantisCallbackEvent
from homeassistant.components.webhook import DOMAIN as WEBHOOK_DOMAIN
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import RESULT_SUCCESS

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("setup_integration")
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
            json=Message(
                remote_event=RemoteEvent(
                    remote_action_id=remote_action_id, event_status=RESULT_SUCCESS
                )
            ).to_dict(),
        )
        await hass.async_block_till_done()

        assert resp.status == 200
        assert callback_event.done()
        assert callback_event.result() == RESULT_SUCCESS
