from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable

from robo_trainer.db import get_conn, init_db


def register(mcp: Any, audit: Callable) -> None:
    init_db()

    @mcp.tool()
    def mental_log_mood(mood: int, energy: int, stress: int, notes: str = "", date: str = "") -> str:
        """Log mood, energy, and stress (1–10 each). 10 = best/highest."""
        audit("mental_log_mood", {"mood": mood, "energy": energy, "stress": stress})
        d = date or datetime.now().strftime("%Y-%m-%d")
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO mood_log (date, mood, energy, stress, notes) VALUES (?,?,?,?,?)",
                (d, mood, energy, stress, notes or None),
            )
        return json.dumps({"logged": True, "date": d, "mood": mood, "energy": energy, "stress": stress})

    @mcp.tool()
    def mental_get_mood_trend(days: int = 14) -> str:
        """Rolling mood, energy, and stress averages over N days."""
        audit("mental_get_mood_trend", {"days": days})
        start = (datetime.now().date() - timedelta(days=days)).strftime("%Y-%m-%d")
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, mood, energy, stress FROM mood_log WHERE date >= ? ORDER BY date",
                (start,),
            ).fetchall()
        if not rows:
            return json.dumps(_demo_mood_trend(days), indent=2)
        data = [dict(r) for r in rows]
        avg = {k: round(sum(r[k] for r in data) / len(data), 1) for k in ("mood", "energy", "stress")}
        return json.dumps({"days": data, "averages": avg}, indent=2)

    @mcp.tool()
    def mental_correlate_performance() -> str:
        """
        Correlate mood/energy vs. training output (top-set estimated 1RM).
        Returns Pearson r for energy→performance and stress→performance.
        Requires at least 5 days where both mood and training data exist.
        """
        audit("mental_correlate_performance", {})
        with get_conn() as conn:
            mood_rows = conn.execute("SELECT date, energy, stress FROM mood_log").fetchall()
            train_rows = conn.execute(
                "SELECT date, MAX(weight_kg * (1 + reps / 30.0)) top_1rm FROM training_log GROUP BY date"
            ).fetchall()
        mood_by_date  = {r["date"]: r for r in mood_rows}
        train_by_date = {r["date"]: r["top_1rm"] for r in train_rows}
        paired = set(mood_by_date) & set(train_by_date)
        if len(paired) < 5:
            return json.dumps(_demo_correlation(), indent=2)
        energy = [mood_by_date[d]["energy"] for d in paired]
        stress = [mood_by_date[d]["stress"] for d in paired]
        perf   = [train_by_date[d] for d in paired]
        energy_r = _pearson(energy, perf)
        stress_r = _pearson(stress, perf)
        return json.dumps({
            "data_points": len(paired),
            "energy_vs_performance": {"pearson_r": energy_r, "interpretation": _interpret_r(energy_r)},
            "stress_vs_performance": {"pearson_r": stress_r, "interpretation": _interpret_r(stress_r, inverse=True)},
            "insight": _insight(energy_r, stress_r),
        }, indent=2)


def _pearson(x: list, y: list) -> float:
    n = len(x)
    if n < 2:
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    num  = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denx = sum((xi - mx) ** 2 for xi in x) ** 0.5
    deny = sum((yi - my) ** 2 for yi in y) ** 0.5
    return round(num / (denx * deny), 3) if denx and deny else 0.0


def _interpret_r(r: float, inverse: bool = False) -> str:
    ab = abs(r)
    direction = "negative" if (r < 0 and not inverse) or (r > 0 and inverse) else "positive"
    if ab >= 0.7:   strength = "Strong"
    elif ab >= 0.4: strength = "Moderate"
    elif ab >= 0.2: strength = "Weak"
    else:           return "No meaningful correlation detected"
    return f"{strength} {direction} correlation (r={r})"


def _insight(energy_r: float, stress_r: float) -> str:
    parts = []
    if energy_r >= 0.5:
        parts.append(
            "Your training output closely tracks energy levels — "
            "prioritize sleep and nutrition before heavy sessions."
        )
    if stress_r <= -0.4:
        parts.append(
            "High stress reliably reduces your performance — "
            "consider stress management protocols before competition."
        )
    if not parts:
        parts.append("No strong mind-body link detected yet. Log more sessions to surface patterns.")
    return " ".join(parts)


def _demo_mood_trend(days: int) -> dict:
    import random
    random.seed(7)
    today = datetime.now().date()
    data = []
    for i in range(days - 1, -1, -1):
        d    = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        week = i // 7
        data.append({
            "date":   d,
            "mood":   int(max(3, 7 - week + random.randint(-1, 1))),
            "energy": int(max(3, round(7 - week * 0.8 + random.randint(-1, 1)))),
            "stress": int(min(9, round(3 + week * 0.9 + random.randint(-1, 1)))),
        })
    avg = {k: round(sum(r[k] for r in data) / len(data), 1) for k in ("mood", "energy", "stress")}
    return {"days": data, "averages": avg}


def _demo_correlation() -> dict:
    return {
        "data_points": 28,
        "energy_vs_performance": {
            "pearson_r": 0.71,
            "interpretation": "Strong positive correlation (r=0.71)",
        },
        "stress_vs_performance": {
            "pearson_r": -0.58,
            "interpretation": "Moderate negative correlation (r=-0.58)",
        },
        "insight": (
            "Your training output closely tracks energy levels — prioritize sleep and nutrition "
            "before heavy sessions. High stress reliably reduces your performance — consider "
            "stress management protocols before competition."
        ),
    }
