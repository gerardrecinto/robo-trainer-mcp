"""Small input checks so bad numbers return a clear error instead of a wrong answer."""
from __future__ import annotations

import json
import math
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


def _error(message: str) -> str:
    return json.dumps({"error": message})


SAMPLE_NOTE = "No data logged yet, so these are made-up sample values that show the output shape. They are not yours."


def sample(data: Any, note: str = SAMPLE_NOTE) -> str:
    """Wrap sample output so nobody mistakes it for real results."""
    return json.dumps({"sample_data": True, "note": note, "data": data}, indent=2)
