from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable

from robo_trainer.db import get_conn, init_db


def _epley_1rm(weight: float, reps: int) -> float:
    if reps == 1:
        return weight
    return round(weight * (1 + reps / 30.0), 1)


def register(mcp: Any, audit: Callable) -> None:
    init_db()

    @mcp.tool()
    def training_log_set(
        exercise: str,
        weight_kg: float,
        reps: int,
        rpe: float = 0.0,
        date: str = "",
        notes: str = "",
    ) -> str:
        """Log a training set with weight, reps, and optional RPE (1–10)."""
        audit("training_log_set", {"exercise": exercise, "weight_kg": weight_kg, "reps": reps})
        d = date or datetime.now().strftime("%Y-%m-%d")
        with get_conn() as conn:
            last = conn.execute(
                "SELECT MAX(set_number) n FROM training_log WHERE date=? AND exercise=?",
                (d, exercise),
            ).fetchone()
            set_num = (last["n"] or 0) + 1
            conn.execute(
                "INSERT INTO training_log (date, exercise, set_number, weight_kg, reps, rpe, notes) "
                "VALUES (?,?,?,?,?,?,?)",
                (d, exercise, set_num, weight_kg, reps, rpe or None, notes or None),
            )
        return json.dumps({
            "logged": {"exercise": exercise, "set": set_num, "weight_kg": weight_kg, "reps": reps, "rpe": rpe},
            "estimated_1rm_kg": _epley_1rm(weight_kg, reps),
        })

    @mcp.tool()
    def training_get_prs() -> str:
        """Personal records (heaviest set) for every exercise."""
        audit("training_get_prs", {})
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT exercise, MAX(weight_kg) weight_kg, reps, date "
                "FROM training_log GROUP BY exercise ORDER BY weight_kg DESC"
            ).fetchall()
        if not rows:
            return json.dumps(_demo_prs(), indent=2)
        return json.dumps([
            {
                "exercise": r["exercise"],
                "weight_kg": r["weight_kg"],
                "reps": r["reps"],
                "estimated_1rm_kg": _epley_1rm(r["weight_kg"], r["reps"]),
                "date": r["date"],
            }
            for r in rows
        ], indent=2)

    @mcp.tool()
    def training_calculate_1rm(weight_kg: float, reps: int) -> str:
        """Epley 1RM estimate with full percentage chart (60%–95%)."""
        audit("training_calculate_1rm", {"weight_kg": weight_kg, "reps": reps})
        e1rm = _epley_1rm(weight_kg, reps)
        return json.dumps({
            "input": {"weight_kg": weight_kg, "reps": reps},
            "estimated_1rm_kg": e1rm,
            "percentage_chart": {
                f"{pct}%": round(e1rm * pct / 100, 1)
                for pct in (60, 65, 70, 75, 80, 85, 90, 95)
            },
        }, indent=2)

    @mcp.tool()
    def training_get_volume_trend(exercise: str, weeks: int = 4) -> str:
        """Weekly volume (sets × weight × reps) trend for an exercise."""
        audit("training_get_volume_trend", {"exercise": exercise, "weeks": weeks})
        start = (datetime.now().date() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, SUM(weight_kg * reps) volume FROM training_log "
                "WHERE exercise=? AND date >= ? GROUP BY date ORDER BY date",
                (exercise, start),
            ).fetchall()
        if not rows:
            return json.dumps(_demo_volume_trend(exercise, weeks), indent=2)
        weekly: dict[str, float] = {}
        for r in rows:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            week_start = (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")
            weekly[week_start] = weekly.get(week_start, 0) + (r["volume"] or 0)
        return json.dumps({
            "exercise": exercise,
            "weeks": weeks,
            "trend": [{"week_of": k, "volume_kg": round(v, 1)} for k, v in sorted(weekly.items())],
        }, indent=2)

    @mcp.tool()
    def training_get_session_history(exercise: str, limit: int = 10) -> str:
        """Recent training sessions for a specific exercise."""
        audit("training_get_session_history", {"exercise": exercise, "limit": limit})
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, set_number, weight_kg, reps, rpe FROM training_log "
                "WHERE exercise=? ORDER BY date DESC, set_number LIMIT ?",
                (exercise, limit * 5),
            ).fetchall()
        if not rows:
            return json.dumps(_demo_session_history(exercise), indent=2)
        sessions: dict = {}
        for r in rows:
            sessions.setdefault(r["date"], []).append({
                "set": r["set_number"], "weight_kg": r["weight_kg"],
                "reps": r["reps"], "rpe": r["rpe"],
            })
        return json.dumps([
            {
                "date": d,
                "sets": sets,
                "top_set_1rm": max(_epley_1rm(s["weight_kg"], s["reps"]) for s in sets),
            }
            for d, sets in list(sessions.items())[:limit]
        ], indent=2)


def _demo_prs() -> list[dict]:
    return [
        {"exercise": "squat", "weight_kg": 180.0, "reps": 3, "estimated_1rm_kg": 198.0, "date": "2024-01-10"},
        {"exercise": "deadlift", "weight_kg": 220.0, "reps": 2, "estimated_1rm_kg": 234.7, "date": "2024-01-12"},
        {"exercise": "bench_press", "weight_kg": 120.0, "reps": 3, "estimated_1rm_kg": 132.0, "date": "2024-01-08"},
    ]


def _demo_volume_trend(exercise: str, weeks: int) -> dict:
    base = [12400, 13100, 14200, 14800, 15300, 15100]
    today = datetime.now().date()
    return {
        "exercise": exercise,
        "weeks": weeks,
        "trend": [
            {
                "week_of": (today - timedelta(weeks=weeks - i)).strftime("%Y-%m-%d"),
                "volume_kg": base[min(i, len(base) - 1)],
            }
            for i in range(weeks)
        ],
    }


def _demo_session_history(exercise: str) -> list[dict]:
    return [
        {"date": "2024-01-12", "sets": [
            {"set": 1, "weight_kg": 160.0, "reps": 5, "rpe": 7.0},
            {"set": 2, "weight_kg": 170.0, "reps": 4, "rpe": 8.0},
            {"set": 3, "weight_kg": 175.0, "reps": 3, "rpe": 8.5},
        ], "top_set_1rm": 192.5},
        {"date": "2024-01-08", "sets": [
            {"set": 1, "weight_kg": 155.0, "reps": 5, "rpe": 7.0},
            {"set": 2, "weight_kg": 165.0, "reps": 5, "rpe": 8.0},
            {"set": 3, "weight_kg": 170.0, "reps": 4, "rpe": 8.5},
        ], "top_set_1rm": 186.7},
    ]
