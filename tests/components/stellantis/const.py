"""Constants used on Stellantis tests."""

from stellantis.model import (
    RemoteDoneEventStatus,
    RemoteEventStatus,
    RemoteEventType,
    RemoteFailedEventStatus,
    RemotePendingEventStatus,
)

RESULT_PENDING = RemoteEventStatus(
    RemoteEventType.PENDING, RemotePendingEventStatus.ACCEPTED
)
RESULT_SUCCESS = RemoteEventStatus(RemoteEventType.DONE, RemoteDoneEventStatus.SUCCESS)
RESULT_FAILED = RemoteEventStatus(
    RemoteEventType.DONE,
    RemoteDoneEventStatus.FAILED,
    RemoteFailedEventStatus.GENERAL_ERROR,
)
