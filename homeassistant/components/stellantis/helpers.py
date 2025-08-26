"""Helpers for stellantis implementation."""

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
    _program = AirConditioningProgram(**program.to_dict(), actions_type=ActionType.SET)
    return Remote(
        preconditioning=RemotePreconditioning(
            air_conditioning=RemotePreconditioningAirConditioning(programs=[_program])
        )
    )
