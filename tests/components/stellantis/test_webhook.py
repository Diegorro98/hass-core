"""Test Stellantis webhook."""

import pytest
from stellantis.model import Message, RemoteEvent, RemoteEventStatus

from homeassistant.components.stellantis.webhook import StellantisCallbackEvent
from homeassistant.components.webhook import DOMAIN as WEBHOOK_DOMAIN
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import RESULT_FAILED, RESULT_PENDING, RESULT_SUCCESS

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize("result", [RESULT_SUCCESS, RESULT_FAILED])
async def test_webhook_result(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    result: RemoteEventStatus,
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
                    remote_action_id=remote_action_id, event_status=result
                )
            ).to_dict(),
        )
        await hass.async_block_till_done()

        assert resp.status == 200
        assert callback_event.done()
        assert callback_event.result() == result


@pytest.mark.usefixtures("setup_integration")
async def test_webhook_result_pending(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test that a pending result doesn't stop waiting for the final result."""
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
                    remote_action_id=remote_action_id, event_status=RESULT_PENDING
                )
            ).to_dict(),
        )
        await hass.async_block_till_done()

        assert resp.status == 200
        assert not callback_event.done()

        resp = await client.post(
            "/api/webhook/" + config_entry.data[CONF_WEBHOOK_ID],
            json=Message(
                remote_event=RemoteEvent(
                    remote_action_id=remote_action_id, event_status=RESULT_SUCCESS
                )
            ).to_dict(),
        )
        await hass.async_block_till_done()

        assert callback_event.done()
        assert callback_event.result() == RESULT_SUCCESS
