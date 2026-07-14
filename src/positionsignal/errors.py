"""Friendly domain errors for the PositionSignal workflow."""

from __future__ import annotations


class DataProblem(ValueError):
    """An expected, user-fixable problem with data or analysis setup."""


def friendly_message(exc: Exception) -> str:
    """Return a useful public message without leaking implementation details."""
    if isinstance(exc, DataProblem):
        return str(exc)
    return "PositionSignal could not finish that step. Check the data and settings, then try again."

