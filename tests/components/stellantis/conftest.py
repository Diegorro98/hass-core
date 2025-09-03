"""Tests for the Stellantis integration."""

from copy import deepcopy
import time
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from stellantis.client import Client as StellantisClient
from stellantis.model import (
    Callback,
    CallbackRef,
    CallbackStatus,
    CallbackSubscribe,
    CallbackType,
    ChargingCapabilitiesParameters,
    ChargingImmediateCapabilities,
    ChargingPreferencesCapabilities,
    ChargingScheduleCapabilities,
    ChargingScheduleProgramsCapabilities,
    Message,
    Motorization,
    OnboardCapabilities,
    OnboardCapabilitiesEnum,
    OnboardCapabilitiesRemoteFunctions,
    OnboardCapability,
    OnboardCapabilityCharging,
    OnboardCapabilityPreconditioning,
    PreconditioningCapabilitiesParameters,
    PreconditioningProgramsCapabilities,
    RemoteEvent,
    RemoteEventStatus,
    RemotePostResponse,
    Scopes,
    Status,
    UserCallback,
    Vehicle,
    VehicleBranding,
    VehicleEmbedded,
    VehicleExtension,
    Vehicles,
    VehiclesEmbedded,
    Webhook,
)

from homeassistant.components.stellantis.const import CONF_BRAND, DOMAIN, Brand
from homeassistant.components.webhook import DOMAIN as WEBHOOK_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_WEBHOOK_ID,
    EVENT_CALL_SERVICE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import RESULT_SUCCESS

from tests.common import MockConfigEntry, load_fixture
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
FAKE_REFRESH_TOKEN = "some-refresh-token"
FAKE_AUTH_IMPL = "conftest-imported-cred"

SERVER_ACCESS_TOKEN = {
    "refresh_token": "server-refresh-token",
    "access_token": "server-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


FIXTURE_VEHICLE_DETAILS = Vehicle(
    vin="TEST_VIN_00000000",
    id="test_id",
    motorization=Motorization.HYBRID,
    embedded=VehicleEmbedded(
        extension=VehicleExtension(
            branding=VehicleBranding(
                brand=Brand.PEUGEOT.value,
                label="SUV 3008",
            ),
            onboard_capabilities=OnboardCapabilities(
                data=list(OnboardCapabilitiesEnum.__members__.values()),
                remote=OnboardCapabilitiesRemoteFunctions(
                    preconditioning=OnboardCapabilityPreconditioning(
                        supported=True,
                        scope_name=Scopes.REMOTE_PRECONDITIONING_WRITE,
                        parameters=PreconditioningCapabilitiesParameters(
                            programs=PreconditioningProgramsCapabilities(size=4),
                            immediate=True,
                        ),
                    ),
                    door=OnboardCapability(
                        supported=True,
                        scope_name=Scopes.REMOTE_DOOR_WRITE,
                    ),
                    horn=OnboardCapability(
                        supported=True, scope_name=Scopes.REMOTE_HORN_WRITE
                    ),
                    charging=OnboardCapabilityCharging(
                        supported=True,
                        scope_name=Scopes.REMOTE_CHARGING_WRITE,
                        parameters=ChargingCapabilitiesParameters(
                            immediate=ChargingImmediateCapabilities(
                                start=True, stop=True
                            ),
                            schedule=ChargingScheduleCapabilities(
                                programs=ChargingScheduleProgramsCapabilities(
                                    supported=True, size=4
                                ),
                                next_delayed_time=True,
                            ),
                            preferences=ChargingPreferencesCapabilities(
                                level=True, type=True
                            ),
                        ),
                    ),
                    lights=OnboardCapability(
                        supported=True, scope_name=Scopes.REMOTE_LIGHTS_WRITE
                    ),
                    wakeup=OnboardCapability(
                        supported=True, scope_name=Scopes.REMOTE_WAKEUP_WRITE
                    ),
                    navigation=OnboardCapability(
                        supported=True, scope_name=Scopes.REMOTE_NAVIGATION_WRITE
                    ),
                ),
            ),
        )
    ),
    links={},
)
FIXTURE_VEHICLE_STATUS = Status.from_json(
    load_fixture("vehicle_status.json", "stellantis")
)


@pytest.fixture(name="token_expiration_time")
def mock_token_expiration_time() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 86400


@pytest.fixture(name="token_entry")
def mock_token_entry(token_expiration_time: float) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "refresh_token": FAKE_REFRESH_TOKEN,
        "access_token": FAKE_ACCESS_TOKEN,
        "type": "Bearer",
        "expires_at": token_expiration_time,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(
    token_entry: dict[str, Any], request: pytest.FixtureRequest
) -> MockConfigEntry:
    """Fixture for a config entry."""

    if hasattr(request, "param"):
        overwriting_data = cast(dict, request.param)
    else:
        overwriting_data = {}

    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BRAND: Brand.PEUGEOT.value,
            CONF_COUNTRY: "ES",
            CONF_WEBHOOK_ID: "mock-webhook-id",
            "token": token_entry,
            **overwriting_data,
        },
        unique_id="example@domain.com",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant,
    platforms: list[Platform],
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> bool:
    """Fixture to setup the integration."""
    config_entry.add_to_hass(hass)
    hass.config.external_url = "https://example.com"
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    with (
        patch("homeassistant.components.stellantis.PLATFORMS", platforms),
        patch(
            "homeassistant.components.stellantis.StellantisClient", return_value=client
        ),
    ):
        return await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.fixture(name="vehicle_details")
def vehicle_fixture() -> Vehicle:
    """Define a vehicle fixture."""
    return deepcopy(FIXTURE_VEHICLE_DETAILS)


@pytest.fixture(name="vehicle_status")
def vehicle_status_fixture() -> Status:
    """Define a vehicle fixture."""
    return deepcopy(FIXTURE_VEHICLE_STATUS)


@pytest.fixture(name="client")
def mock_client(vehicle_details: Vehicle, vehicle_status: Status) -> MagicMock:
    """Fixture to mock Client from Stellantis."""

    mock = MagicMock(
        autospec=StellantisClient,
    )

    mock.get_user_remote_by_id = AsyncMock(
        return_value=UserCallback(
            id="a test callback id",
            status=CallbackStatus.RUNNING,
            subscribe=CallbackSubscribe(
                type=[CallbackType.REMOTE],
                callback=Callback(
                    webhook=Webhook(
                        target="/api/webhook/mock-webhook-id",
                        name="a test webhook",
                    )
                ),
            ),
            links={},
        )
    )

    mock.get_vehicles_by_device = AsyncMock(
        return_value=Vehicles(
            embedded=VehiclesEmbedded(vehicles=[vehicle_details]),
            total=1,
            total_page=1,
            current_page=1,
            links={},
        )
    )

    mock.get_vehicle_status = AsyncMock(return_value=vehicle_status)
    mock.send_remote_to_vhl = AsyncMock()
    mock.set_user_vehicle_remote = AsyncMock(
        return_value=CallbackRef(callback_id="mock-callback-id")
    )
    mock.delete_user_remote = AsyncMock()

    return mock


@pytest.fixture
async def send_webhook_result(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    client: MagicMock,
    request: pytest.FixtureRequest,
):
    """Fixture to return a function to send webhook results."""
    if hasattr(request, "param"):
        results = cast(list[RemoteEventStatus | Any], request.param)
    else:
        results = [RESULT_SUCCESS]
    assert await async_setup_component(hass, WEBHOOK_DOMAIN, {})
    hass_client = await hass_client_no_auth()

    client.send_remote_to_vhl.return_value = RemotePostResponse(
        remote_action_id="test_remote_action_id"
    )

    async def _send_webhook_result(_) -> None:
        for result in results:
            await hass_client.post(
                "/api/webhook/" + config_entry.data[CONF_WEBHOOK_ID],
                json=Message(
                    remote_event=RemoteEvent(
                        remote_action_id="test_remote_action_id",
                        event_status=result,
                    )
                ).to_dict()
                if isinstance(result, RemoteEventStatus)
                else result,
            )

    hass.bus.async_listen_once(EVENT_CALL_SERVICE, _send_webhook_result)

    yield

    await hass.async_block_till_done()
