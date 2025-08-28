"""Helpers for stellantis implementation."""

from datetime import time, timedelta

from stellantis.model import (
    ActionType,
    AirConditioningProgram,
    PreconditioningProgram,
    Remote,
    RemotePreconditioning,
    RemotePreconditioningAirConditioning,
)


def preconditioning_program_setter_body(program: PreconditioningProgram) -> Remote:
    """Return the body for setting a preconditioning program."""
    _program = AirConditioningProgram.from_dict(program.to_dict())
    _program.actions_type = ActionType.SET
    return Remote(
        preconditioning=RemotePreconditioning(
            air_conditioning=RemotePreconditioningAirConditioning(programs=[_program])
        )
    )


def time_to_iso_duration(t: time | timedelta) -> str:
    """Convert a time object to an ISO 8601 duration string."""
    if isinstance(t, time):
        hour = t.hour
        minute = t.minute
    elif isinstance(t, timedelta):
        hour = t.seconds // 3600
        minute = t.seconds % 3600 // 60

    match hour, minute:
        case 0, 0:
            return "PT0S"
        case 0, _:
            return f"PT{minute}M"
        case _, 0:
            return f"PT{hour}H"

    return f"PT{hour}H{minute}M"
