"""Helpers for Stellantis tests."""

from asyncio import sleep


def create_future_result(result):
    """Create a Generator object to mock Future class results."""
    yield from sleep(0).__await__()
    return result
