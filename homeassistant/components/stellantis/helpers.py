"""Helpers for stellantis implementation."""

from typing import Any


def preconditioning_program_setter_body(program: dict[str, Any]) -> dict[str, Any]:
    """Return the body for setting a preconditioning program."""
    return {
        "preconditioning": {
            "airConditioning": {
                "programs": [
                    {
                        **program,
                        "actionsType": "Set",
                    }
                ],
            }
        }
    }
