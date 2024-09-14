"""Tests for home_connect time entities."""

from collections.abc import Awaitable, Callable, Generator
from datetime import time
from unittest.mock import MagicMock, Mock

from homeconnect.api import HomeConnectError
import pytest

from homeassistant.components.home_connect.const import ATTR_VALUE
from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, Platform
from homeassistant.core import HomeAssistant

from .conftest import get_all_appliances

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.TIME]


async def test_time(
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: Mock,
) -> None:
    """Test time entity."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "setting_key"),
    [
        (
            f"{TIME_DOMAIN.lower()}.oven_alarm_clock",
            "BSH.Common.Setting.AlarmClock",
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_time_entity_functionality(
    appliance: Mock,
    entity_id: str,
    setting_key: str,
    bypass_throttle: Generator[None],
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test time entity functionality."""
    get_appliances.return_value = [appliance]
    current_value = 59
    appliance.status.update({setting_key: {ATTR_VALUE: current_value}})

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    assert hass.states.is_state(entity_id, str(time(second=current_value)))

    new_value = 30
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TIME: time(second=new_value),
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    appliance.set_setting.assert_called_once_with(setting_key, new_value)


@pytest.mark.parametrize("problematic_appliance", ["Oven"], indirect=True)
@pytest.mark.parametrize(
    ("entity_id", "setting_key", "mock_attr"),
    [
        (
            f"{TIME_DOMAIN.lower()}.oven_alarm_clock",
            "BSH.Common.Setting.AlarmClock",
            "set_setting",
        ),
    ],
)
@pytest.mark.usefixtures("bypass_throttle")
async def test_time_entity_error(
    problematic_appliance: Mock,
    entity_id: str,
    setting_key: str,
    mock_attr: str,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
) -> None:
    """Test time entity error."""
    get_appliances.return_value = [problematic_appliance]

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    problematic_appliance.status.update({setting_key: {}})
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    with pytest.raises(HomeConnectError):
        getattr(problematic_appliance, mock_attr)()

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TIME: time(minute=1),
        },
        blocking=True,
    )
    assert getattr(problematic_appliance, mock_attr).call_count == 2
