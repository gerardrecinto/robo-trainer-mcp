from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from robo_trainer.db import get_conn, init_db
from robo_trainer.validation import check, check_date, check_note, sample


def _readiness_score(sleep_hours: float, sleep_quality: int, soreness: int, stress: int) -> float:
    """0-100 readiness score. A simple heuristic, not a validated clinical tool.

    Sleep earns full marks at 7 hours, the minimum most adults need (AASM and Sleep Research Society
    consensus: at least 7 hours). Quality, soreness and stress are self-rated and weighted by hand.
    """
    sleep_score   = min(sleep_hours / 7.0, 1.0) * 40
    quality_score = (sleep_quality / 10.0) * 25
    sore_score    = ((10 - soreness) / 9.0) * 20
    stress_score  = ((10 - stress) / 9.0) * 15
    return round(sleep_score + quality_score + sore_score + stress_score, 1)


def register(mcp: Any, audit: Callable) -> None:
    init_db()

    @mcp.tool()
    def recovery_log_sleep(hours: float, quality: int, hrv_ms: float = 0, notes: str = "", date: str = "") -> str:
        """Log sleep: hours slept, quality (1–10), optional HRV in ms."""
        audit("recovery_log_sleep", {"hours": hours, "quality": quality})
        err = check(hours=(hours, 0, 24), quality=(quality, 1, 10, True), hrv_ms=(hrv_ms, 0, 300))
        err = err or check_date(date=date) or check_note(notes)
        if err:
            return err
        d = date or datetime.now().strftime("%Y-%m-%d")
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sleep_log (date, hours, quality, hrv_ms, notes) VALUES (?,?,?,?,?)",
                (d, hours, quality, hrv_ms or None, notes or None),
            )
        return json.dumps({"logged": True, "date": d, "hours": hours, "quality": quality})

    @mcp.tool()
    def recovery_get_sleep_trend(days: int = 14) -> str:
        """Sleep metrics trend over N days."""
        audit("recovery_get_sleep_trend", {"days": days})
        err = check(days=(days, 1, 3650, True))
        if err:
            return err
        start = (datetime.now().date() - timedelta(days=days)).strftime("%Y-%m-%d")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, hours, quality, hrv_ms FROM sleep_log WHERE date >= ? ORDER BY date",
                (start,),
            ).fetchall()
        if not rows:
            return sample(_demo_sleep_trend(days))
        data = [dict(r) for r in rows]
        avg_hours   = round(sum(r["hours"] for r in data) / len(data), 2)
        avg_quality = round(sum(r["quality"] for r in data) / len(data), 1)
        hrv_vals    = [r["hrv_ms"] for r in data if r["hrv_ms"]]
        avg_hrv     = round(sum(hrv_vals) / len(hrv_vals), 1) if hrv_vals else None
        return json.dumps({
            "days": data,
            "averages": {"hours": avg_hours, "quality": avg_quality, "hrv_ms": avg_hrv},
            "guidance": (
                "Average sleep meets the 7 hour adult minimum."
                if avg_hours >= 7 else
                "Average sleep is under the 7 hour adult minimum. Sleep is the cheapest recovery tool to fix first."
            ),
        }, indent=2)

    @mcp.tool()
    def recovery_calculate_readiness(sleep_hours: float, sleep_quality: int, soreness_1_10: int, stress_1_10: int) -> str:
        """Calculate a 0–100 training readiness score from four inputs."""
        audit("recovery_calculate_readiness", {"sleep_hours": sleep_hours, "sleep_quality": sleep_quality})
        err = check(
            sleep_hours=(sleep_hours, 0, 24), sleep_quality=(sleep_quality, 1, 10, True),
            soreness_1_10=(soreness_1_10, 1, 10, True), stress_1_10=(stress_1_10, 1, 10, True),
        )
        if err:
            return err
        score = _readiness_score(sleep_hours, sleep_quality, soreness_1_10, stress_1_10)
        if score >= 80:
            rec = "High readiness — push intensity today."
        elif score >= 60:
            rec = "Moderate readiness — train as planned, avoid maximal attempts."
        elif score >= 40:
            rec = "Low readiness — light technique session or active recovery recommended."
        else:
            rec = "Very low readiness — rest day strongly recommended."
        return json.dumps({
            "inputs": {
                "sleep_hours": sleep_hours,
                "sleep_quality": sleep_quality,
                "soreness": soreness_1_10,
                "stress": stress_1_10,
            },
            "readiness_score": score,
            "recommendation": rec,
        }, indent=2)


def _demo_sleep_trend(days: int) -> dict:
    import random
    random.seed(42)
    today = datetime.now().date()
    day_list = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        week = i // 7
        hours   = max(5.5, 8.0 - week * 0.4 + random.uniform(-0.3, 0.3))
        quality = max(4, 8 - week + random.randint(-1, 1))
        hrv     = max(40, 65 - week * 4 + random.randint(-3, 3))
        day_list.append({"date": d, "hours": round(hours, 1), "quality": quality, "hrv_ms": hrv})
    avg_hours   = round(sum(r["hours"] for r in day_list) / len(day_list), 2)
    avg_quality = round(sum(r["quality"] for r in day_list) / len(day_list), 1)
    avg_hrv     = round(sum(r["hrv_ms"] for r in day_list) / len(day_list), 1)
    return {"days": day_list, "averages": {"hours": avg_hours, "quality": avg_quality, "hrv_ms": avg_hrv}}
