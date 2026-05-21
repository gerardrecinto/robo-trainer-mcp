from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from robo_trainer.db import get_conn, init_db

# Approximate benchmarks based on publicly available competition results
_STANDARDS: dict[str, dict[str, float]] = {
    "log_press":    {"novice": 80,  "regional": 120, "national": 150, "pro": 180},
    "deadlift":     {"novice": 180, "regional": 250, "national": 300, "pro": 360},
    "atlas_stone":  {"novice": 100, "regional": 140, "national": 170, "pro": 200},
    "farmers_walk": {"novice": 100, "regional": 130, "national": 160, "pro": 190},
    "yoke":         {"novice": 200, "regional": 280, "national": 340, "pro": 400},
    "overhead":     {"novice": 70,  "regional": 110, "national": 140, "pro": 165},
}


def register(mcp: Any, audit: Callable) -> None:
    init_db()

    @mcp.tool()
    def strongman_log_event(
        event_name: str,
        implement_weight_kg: float = 0,
        reps: int = 0,
        time_seconds: float = 0,
        distance_meters: float = 0,
        notes: str = "",
        date: str = "",
    ) -> str:
        """Log a strongman event: weight, reps, time, or distance."""
        audit("strongman_log_event", {"event_name": event_name, "implement_weight_kg": implement_weight_kg})
        d = date or datetime.now().strftime("%Y-%m-%d")
        key = event_name.lower().replace(" ", "_")
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO event_log (date, event_name, implement_weight_kg, reps, time_seconds, distance_meters, notes) "
                "VALUES (?,?,?,?,?,?,?)",
                (d, key, implement_weight_kg or None, reps or None,
                 time_seconds or None, distance_meters or None, notes or None),
            )
        return json.dumps({"logged": event_name, "date": d, "weight_kg": implement_weight_kg})

    @mcp.tool()
    def strongman_get_event_prs() -> str:
        """Personal records for all strongman events."""
        audit("strongman_get_event_prs", {})
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT event_name, MAX(implement_weight_kg) weight_kg, "
                "MAX(reps) max_reps, MIN(time_seconds) best_time_s "
                "FROM event_log GROUP BY event_name"
            ).fetchall()
        if not rows:
            return json.dumps(_demo_event_prs(), indent=2)
        return json.dumps([dict(r) for r in rows], indent=2)

    @mcp.tool()
    def strongman_get_event_history(event_name: str) -> str:
        """Progress history for a specific event."""
        audit("strongman_get_event_history", {"event_name": event_name})
        key = event_name.lower().replace(" ", "_")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, implement_weight_kg, reps, time_seconds, distance_meters, notes "
                "FROM event_log WHERE event_name=? ORDER BY date",
                (key,),
            ).fetchall()
        if not rows:
            return json.dumps(_demo_event_history(event_name), indent=2)
        return json.dumps([dict(r) for r in rows], indent=2)

    @mcp.tool()
    def strongman_competition_standards(event_name: str, implement_weight_kg: float) -> str:
        """Compare a performance to novice → regional → national → pro standards."""
        audit("strongman_competition_standards", {"event_name": event_name, "implement_weight_kg": implement_weight_kg})
        key = event_name.lower().replace(" ", "_")
        standards = _STANDARDS.get(key)
        if not standards:
            return json.dumps({
                "error": f"No standards data for '{event_name}'.",
                "known_events": list(_STANDARDS.keys()),
            })
        current_level = "below_novice"
        for level in ("pro", "national", "regional", "novice"):
            if implement_weight_kg >= standards[level]:
                current_level = level
                break
        gaps = {
            level: round(standards[level] - implement_weight_kg, 1)
            for level, threshold in standards.items()
            if implement_weight_kg < threshold
        }
        return json.dumps({
            "event": event_name,
            "your_best_kg": implement_weight_kg,
            "standards_kg": standards,
            "current_level": current_level,
            "kg_to_next_level": gaps,
        }, indent=2)


def _demo_event_prs() -> list[dict]:
    return [
        {"event_name": "log_press",    "weight_kg": 120.0, "max_reps": 5, "best_time_s": None},
        {"event_name": "deadlift",     "weight_kg": 280.0, "max_reps": 1, "best_time_s": None},
        {"event_name": "farmers_walk", "weight_kg": 140.0, "max_reps": None, "best_time_s": 15.4},
        {"event_name": "atlas_stone",  "weight_kg": 140.0, "max_reps": 3, "best_time_s": None},
        {"event_name": "yoke",         "weight_kg": 300.0, "max_reps": None, "best_time_s": 12.8},
    ]


def _demo_event_history(event_name: str) -> list[dict]:
    return [
        {"date": "2023-10-01", "implement_weight_kg": 100.0, "reps": 5,  "time_seconds": None, "distance_meters": None, "notes": "First attempt"},
        {"date": "2023-11-15", "implement_weight_kg": 110.0, "reps": 5,  "time_seconds": None, "distance_meters": None, "notes": None},
        {"date": "2024-01-10", "implement_weight_kg": 120.0, "reps": 5,  "time_seconds": None, "distance_meters": None, "notes": "PR"},
    ]
