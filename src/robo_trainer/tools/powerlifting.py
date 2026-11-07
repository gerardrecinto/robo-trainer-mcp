from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from robo_trainer.validation import check

# Original Wilks (1994) polynomial coefficients. The 2020 revision uses different coefficients and a
# numerator of 600. IPF competitions now use IPF GL points, so DOTS is the better modern choice.
_WILKS_MEN = (-216.0475144, 16.2606339, -0.002388645, -0.00113732, 7.01863e-6, -1.291e-8)
_WILKS_WOMEN = (594.31747775582, -27.23842536447, 0.82112226871, -0.00930733913, 4.731582e-5, -9.054e-8)

# DOTS polynomial coefficients
_DOTS_MEN = (-307.75076, 24.0900756, -0.1918759221, 0.0007391293, -1.093e-6)
_DOTS_WOMEN = (-57.96288, 13.6175032, -0.1126655495, 0.0005158568, -1.0706e-6)


def _poly(bw: float, coeffs: tuple) -> float:
    return sum(c * bw ** i for i, c in enumerate(coeffs))


def _wilks(total_kg: float, bw_kg: float, sex: str) -> float:
    coeffs = _WILKS_MEN if sex.lower() in ("m", "male") else _WILKS_WOMEN
    denom = _poly(bw_kg, coeffs)
    return round(total_kg * 500 / denom, 2) if denom > 0 else 0.0


def _dots(total_kg: float, bw_kg: float, sex: str) -> float:
    coeffs = _DOTS_MEN if sex.lower() in ("m", "male") else _DOTS_WOMEN
    denom = _poly(bw_kg, coeffs)
    return round(total_kg * 500 / denom, 2) if denom > 0 else 0.0


def _classify(score: float) -> str:
    """Rough orientation bands. Not an official standard."""
    if score >= 500: return "Elite"
    if score >= 400: return "Very advanced"
    if score >= 300: return "Advanced"
    if score >= 200: return "Intermediate"
    return "Beginner"


def _check_score_inputs(bodyweight_kg: float, total_kg: float, sex: str) -> str | None:
    if sex.strip().lower() not in ("m", "male", "f", "female"):
        return json.dumps({"error": "sex must be 'm' or 'f'."})
    return check(bodyweight_kg=(bodyweight_kg, 30, 300), total_kg=(total_kg, 1, 1500))


def register(mcp: Any, audit: Callable) -> None:

    @mcp.tool()
    def pl_calculate_wilks(bodyweight_kg: float, total_kg: float, sex: str = "m") -> str:
        """Original (1994) Wilks score. sex: 'm' or 'f'. Prefer DOTS for current comparisons."""
        audit("pl_calculate_wilks", {"bodyweight_kg": bodyweight_kg, "total_kg": total_kg, "sex": sex})
        err = _check_score_inputs(bodyweight_kg, total_kg, sex)
        if err:
            return err
        score = _wilks(total_kg, bodyweight_kg, sex)
        return json.dumps({
            "bodyweight_kg": bodyweight_kg,
            "total_kg": total_kg,
            "sex": sex,
            "wilks_score": score,
            "formula": "Wilks (1994)",
            "classification": _classify(score),
            "classification_note": "Rough bands for orientation, not an official standard.",
        }, indent=2)

    @mcp.tool()
    def pl_calculate_dots(bodyweight_kg: float, total_kg: float, sex: str = "m") -> str:
        """DOTS score. sex: 'm' or 'f'."""
        audit("pl_calculate_dots", {"bodyweight_kg": bodyweight_kg, "total_kg": total_kg, "sex": sex})
        err = _check_score_inputs(bodyweight_kg, total_kg, sex)
        if err:
            return err
        score = _dots(total_kg, bodyweight_kg, sex)
        return json.dumps({
            "bodyweight_kg": bodyweight_kg,
            "total_kg": total_kg,
            "sex": sex,
            "dots_score": score,
            "formula": "DOTS",
            "classification": _classify(score),
            "classification_note": "Rough bands for orientation, not an official standard.",
        }, indent=2)

    @mcp.tool()
    def pl_predict_attempts(squat_kg: float, bench_kg: float, deadlift_kg: float) -> str:
        """Suggest opener, 2nd, and 3rd attempts from your current best lifts, in 2.5 kg steps."""
        audit("pl_predict_attempts", {"squat_kg": squat_kg, "bench_kg": bench_kg, "deadlift_kg": deadlift_kg})
        err = check(squat_kg=(squat_kg, 1, 700), bench_kg=(bench_kg, 1, 500), deadlift_kg=(deadlift_kg, 1, 600))
        if err:
            return err
        result: dict = {}
        for lift, kg in (("squat", squat_kg), ("bench", bench_kg), ("deadlift", deadlift_kg)):
            result[lift] = {
                "opener":    round(kg * 0.90 / 2.5) * 2.5,
                "second":    round(kg * 0.97 / 2.5) * 2.5,
                "third_pr":  round(kg * 1.01 / 2.5) * 2.5,
                "third_big": round(kg * 1.04 / 2.5) * 2.5,
            }
        result["projected_total_kg"] = sum(result[lift]["third_pr"] for lift in ("squat", "bench", "deadlift"))
        result["note"] = (
            "Openers near 90 percent of a recent best leave room for a clean start. "
            "Adjust for how the day feels, and only take a third attempt you could make on a bad day."
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    def pl_analyze_sbd_ratio(squat_kg: float, bench_kg: float, deadlift_kg: float) -> str:
        """Identify weakest lift vs. elite squat:bench:deadlift proportions (raw)."""
        audit("pl_analyze_sbd_ratio", {"squat_kg": squat_kg, "bench_kg": bench_kg, "deadlift_kg": deadlift_kg})
        err = check(squat_kg=(squat_kg, 0, 700), bench_kg=(bench_kg, 0, 500), deadlift_kg=(deadlift_kg, 0, 600))
        if err:
            return err
        total = squat_kg + bench_kg + deadlift_kg
        if total <= 0:
            return json.dumps({"error": "squat_kg + bench_kg + deadlift_kg must be greater than 0."})
        ratios = {
            "squat":    round(squat_kg / total * 100, 1),
            "bench":    round(bench_kg / total * 100, 1),
            "deadlift": round(deadlift_kg / total * 100, 1),
        }
        # Typical raw lifter proportions, approximate: S~37%, B~26%, D~37%. Real shares vary with
        # bodyweight, sex and leverages.
        elite = {"squat": 37.0, "bench": 26.0, "deadlift": 37.0}
        deviations = {k: round(ratios[k] - elite[k], 1) for k in elite}
        weakest = min(deviations, key=deviations.get)
        return json.dumps({
            "squat_kg": squat_kg, "bench_kg": bench_kg, "deadlift_kg": deadlift_kg,
            "total_kg": total,
            "ratios_pct": ratios,
            "deviation_from_elite_avg": deviations,
            "weakest_lift": weakest,
            "note": "Proportions vary with bodyweight, sex and body leverages. Treat this as a prompt to look closer, not a diagnosis.",
            "recommendation": (
                f"Focus additional volume on {weakest} — "
                f"it is {abs(deviations[weakest])}% below elite proportion."
            ),
        }, indent=2)
