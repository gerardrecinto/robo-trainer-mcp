from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from robo_trainer.db import get_conn, init_db
from robo_trainer.validation import check, sample


def _epley_1rm(weight: float, reps: int) -> float:
    if reps == 1:
        return weight
    return round(weight * (1 + reps / 30.0), 1)


def _brzycki_1rm(weight: float, reps: int) -> float:
    if reps == 1:
        return weight
    return round(weight * 36.0 / (37.0 - reps), 1)


# Approximate %1RM when a set is taken to failure, by reps to failure. This is the widely used
# RPE chart (Tuchscherer). It is an average from lifters, so treat results as estimates.
_PERCENT_BY_REPS_TO_FAILURE = {
    1: 100.0, 2: 95.5, 3: 92.2, 4: 89.2, 5: 86.3, 6: 83.7,
    7: 81.1, 8: 78.6, 9: 76.2, 10: 73.9, 11: 70.7, 12: 68.0,
}


def _percent_for_reps_to_failure(reps_to_failure: float) -> float:
    low = int(reps_to_failure)
    high = min(low + 1, 12)
    if low >= 12:
        return _PERCENT_BY_REPS_TO_FAILURE[12]
    frac = reps_to_failure - low
    a, b = _PERCENT_BY_REPS_TO_FAILURE[low], _PERCENT_BY_REPS_TO_FAILURE[high]
    return a + (b - a) * frac


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
        err = check(weight_kg=(weight_kg, 0.1, 1000), reps=(reps, 1, 100, True), rpe=(rpe, 0, 10))
        if err:
            return err
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
            return sample(_demo_prs())
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
        """Estimate your one-rep max with Epley and Brzycki, plus a percentage chart (60%-95%)."""
        audit("training_calculate_1rm", {"weight_kg": weight_kg, "reps": reps})
        err = check(weight_kg=(weight_kg, 0.1, 1000), reps=(reps, 1, 30, True))
        if err:
            return err
        e1rm = _epley_1rm(weight_kg, reps)
        result = {
            "input": {"weight_kg": weight_kg, "reps": reps},
            "estimated_1rm_kg": e1rm,
            "brzycki_1rm_kg": _brzycki_1rm(weight_kg, reps) if reps < 37 else None,
            "percentage_chart": {
                f"{pct}%": round(e1rm * pct / 100, 1)
                for pct in (60, 65, 70, 75, 80, 85, 90, 95)
            },
        }
        if reps > 10:
            result["note"] = (
                "Rep-based 1RM formulas lose accuracy above about 10 reps. "
                "Use a heavier set of 1-5 reps for a more reliable estimate."
            )
        return json.dumps(result, indent=2)

    @mcp.tool()
    def training_estimate_1rm_from_rpe(weight_kg: float, reps: int, rpe: float) -> str:
        """Estimate your one-rep max from a set and how hard it felt (RPE 5-10, half steps allowed)."""
        audit("training_estimate_1rm_from_rpe", {"weight_kg": weight_kg, "reps": reps, "rpe": rpe})
        err = check(weight_kg=(weight_kg, 0.1, 1000), reps=(reps, 1, 12, True), rpe=(rpe, 5, 10))
        if err:
            return err
        reps_in_reserve = 10 - rpe
        reps_to_failure = reps + reps_in_reserve
        if reps_to_failure > 12:
            return json.dumps({"error": "reps plus reps in reserve must be 12 or fewer for this estimate."})
        percent = _percent_for_reps_to_failure(reps_to_failure)
        return json.dumps({
            "input": {"weight_kg": weight_kg, "reps": reps, "rpe": rpe},
            "reps_in_reserve": reps_in_reserve,
            "percent_of_1rm": round(percent, 1),
            "estimated_1rm_kg": round(weight_kg / (percent / 100.0), 1),
            "note": "RPE-based estimates are averages. Your own numbers will differ, and they are only as good as your RPE rating.",
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
            return sample(_demo_volume_trend(exercise, weeks))
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
                "WHERE exercise=? ORDER BY date DESC, set_number",
                (exercise,),
            ).fetchall()
        if not rows:
            return sample(_demo_session_history(exercise))
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

    @mcp.tool()
    def training_log_bodyweight(weight_kg: float, date: str = "") -> str:
        """Log bodyweight in kg for a given date (defaults to today)."""
        audit("training_log_bodyweight", {"weight_kg": weight_kg})
        err = check(weight_kg=(weight_kg, 20, 400))
        if err:
            return err
        d = date or datetime.now().strftime("%Y-%m-%d")
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bodyweight_log (date, weight_kg) VALUES (?,?)",
                (d, weight_kg),
            )
        return json.dumps({"logged": True, "date": d, "weight_kg": weight_kg})

    @mcp.tool()
    def training_get_bodyweight_trend(days: int = 30) -> str:
        """Bodyweight trend over N days: daily log, net change, and average."""
        audit("training_get_bodyweight_trend", {"days": days})
        start = (datetime.now().date() - timedelta(days=days)).strftime("%Y-%m-%d")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, weight_kg FROM bodyweight_log WHERE date >= ? ORDER BY date",
                (start,),
            ).fetchall()
        if not rows:
            return sample(_demo_bodyweight_trend(days))
        data = [dict(r) for r in rows]
        return json.dumps({
            "days": data,
            "starting_kg": data[0]["weight_kg"],
            "latest_kg": data[-1]["weight_kg"],
            "net_change_kg": round(data[-1]["weight_kg"] - data[0]["weight_kg"], 2),
            "average_kg": round(sum(r["weight_kg"] for r in data) / len(data), 2),
        }, indent=2)

    @mcp.tool()
    def training_check_overreaching(exercise: str, weeks: int = 4) -> str:
        """Flag overreaching risk for an exercise: rising volume plus rising RPE with no deload."""
        audit("training_check_overreaching", {"exercise": exercise, "weeks": weeks})
        start = (datetime.now().date() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, weight_kg, reps, rpe FROM training_log "
                "WHERE exercise=? AND date >= ? ORDER BY date",
                (exercise, start),
            ).fetchall()
        if not rows:
            return sample(_demo_overreaching(exercise, weeks))
        weekly_volume: dict[str, float] = {}
        weekly_rpe: dict[str, list[float]] = {}
        for r in rows:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            week_start = (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")
            weekly_volume[week_start] = weekly_volume.get(week_start, 0) + (r["weight_kg"] or 0) * (r["reps"] or 0)
            if r["rpe"]:
                weekly_rpe.setdefault(week_start, []).append(r["rpe"])
        today = datetime.now().date()
        current_week = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        # The current week is still in progress, so its volume looks low. Leave it out until Sunday.
        weeks_sorted = sorted(w for w in weekly_volume if w != current_week or today.weekday() == 6)
        if len(weeks_sorted) < 2:
            return json.dumps({
                "exercise": exercise,
                "risk": "insufficient_data",
                "recommendation": "Log at least two full weeks of sets to assess overreaching risk. The current week is not counted until it ends.",
            }, indent=2)
        volumes = [weekly_volume[w] for w in weeks_sorted]
        avg_rpes = [
            round(sum(weekly_rpe[w]) / len(weekly_rpe[w]), 1) if weekly_rpe.get(w) else None
            for w in weeks_sorted
        ]
        rpe_values = [r for r in avg_rpes if r is not None]
        volume_rising = volumes[-1] > volumes[0] * 1.05
        rpe_rising = len(rpe_values) >= 2 and rpe_values[-1] - rpe_values[0] >= 0.5
        if volume_rising and rpe_rising:
            risk = "elevated"
            rec = "Volume and perceived effort are both climbing with no deload. Consider a deload week."
        elif volume_rising:
            risk = "moderate"
            rec = "Volume is climbing but effort is stable. Monitor recovery, no deload needed yet."
        else:
            risk = "low"
            rec = "Volume is flat or dropping. Overreaching unlikely from this exercise alone."
        return json.dumps({
            "exercise": exercise,
            "weeks_analyzed": len(weeks_sorted),
            "weekly_volume_kg": dict(zip(weeks_sorted, [round(v, 1) for v in volumes], strict=False)),
            "weekly_avg_rpe": dict(zip(weeks_sorted, avg_rpes, strict=False)),
            "risk": risk,
            "recommendation": rec,
        }, indent=2)


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


def _demo_bodyweight_trend(days: int) -> dict:
    today = datetime.now().date()
    base = 88.0
    data = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        weight = round(base - (days - i) * 0.03, 1)
        data.append({"date": d, "weight_kg": weight})
    return {
        "days": data,
        "starting_kg": data[0]["weight_kg"],
        "latest_kg": data[-1]["weight_kg"],
        "net_change_kg": round(data[-1]["weight_kg"] - data[0]["weight_kg"], 2),
        "average_kg": round(sum(r["weight_kg"] for r in data) / len(data), 2),
    }


def _demo_overreaching(exercise: str, weeks: int) -> dict:
    today = datetime.now().date()
    week_keys = [
        (today - timedelta(weeks=weeks - i - 1, days=today.weekday())).strftime("%Y-%m-%d")
        for i in range(weeks)
    ]
    volumes = [12400, 13100, 14200, 15300][:weeks] or [12400]
    rpes = [7.0, 7.5, 8.0, 8.7][:weeks] or [7.0]
    return {
        "exercise": exercise,
        "weeks_analyzed": len(week_keys),
        "weekly_volume_kg": dict(zip(week_keys, volumes, strict=False)),
        "weekly_avg_rpe": dict(zip(week_keys, rpes, strict=False)),
        "risk": "elevated",
        "recommendation": "Volume and perceived effort are both climbing with no deload. Consider a deload week.",
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
