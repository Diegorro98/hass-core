"""Constants used on Stellantis tests."""

from homeassistant.components.stellantis.const import (
    ATTR_EVENT_TYPE,
    ATTR_FAILURE_CAUSE,
    ATTR_STATUS,
    EventStatusType,
    RemoteDoneEventStatus,
)

RESULT_PENDING = {ATTR_EVENT_TYPE: EventStatusType.PENDING.value}
RESULT_SUCCESS = {
    ATTR_EVENT_TYPE: EventStatusType.DONE.value,
    ATTR_STATUS: RemoteDoneEventStatus.SUCCESS.value,
}
RESULT_FAILED = {
    ATTR_EVENT_TYPE: EventStatusType.DONE.value,
    ATTR_STATUS: RemoteDoneEventStatus.FAILED.value,
    ATTR_FAILURE_CAUSE: "mocked_error",
}
