"""Small input checks so bad numbers return a clear error instead of a wrong answer."""
from __future__ import annotations

import json
import math
from datetime import date as _date
from typing import Any


def check(**fields: tuple) -> str | None:
    """Validate named numbers. Each field is (value, low, high) or (value, low, high, True) for whole numbers.

    Returns a JSON error string for the first bad field, or None when everything is fine.
    """
    for name, spec in fields.items():
        value, low, high = spec[0], spec[1], spec[2]
        whole = len(spec) > 3 and spec[3]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return _error(f"{name} must be a number.")
        if whole and int(value) != value:
            return _error(f"{name} must be a whole number.")
        if value < low or value > high:
            return _error(f"{name} must be between {low} and {high}.")
    return None


def check_date(**fields: str) -> str | None:
    """Validate named dates. Each value must be empty (meaning today) or a real YYYY-MM-DD date.

    Returns a JSON error string for the first bad one, or None.
    """
    for name, value in fields.items():
        if value == "":
            continue
        try:
            ok = isinstance(value, str) and len(value) == 10 and _date.fromisoformat(value).isoformat() == value
        except ValueError:
            ok = False
        if not ok:
            return _error(f"{name} must be a real date written YYYY-MM-DD, for example 2026-01-31.")
    return None


def check_name(name: str, value: str, max_length: int = 80) -> str | None:
    """Validate a required short text field."""
    if not isinstance(value, str) or not value.strip():
        return _error(f"{name} must not be empty.")
    if len(value) > max_length:
        return _error(f"{name} must be {max_length} characters or fewer.")
    return None


def check_note(value: str, max_length: int = 1000) -> str | None:
    """Validate an optional free-text note so one call cannot store megabytes."""
    if isinstance(value, str) and len(value) > max_length:
        return _error(f"notes must be {max_length} characters or fewer.")
    return None


def _error(message: str) -> str:
    return json.dumps({"error": message})


SAMPLE_NOTE = "No data logged yet, so these are made-up sample values that show the output shape. They are not yours."


def sample(data: Any, note: str = SAMPLE_NOTE) -> str:
    """Wrap sample output so nobody mistakes it for real results."""
    return json.dumps({"sample_data": True, "note": note, "data": data}, indent=2)
