from __future__ import annotations

import json
from typing import Any, Callable

# Wilks 2020 polynomial coefficients
_WILKS_MEN = (-216.0475144, 16.2606339, -0.002388645, -0.00113732, 7.01863e-6, -1.291e-8)
_WILKS_WOMEN = (594.31747775582, -27.23842536447, 0.82112226871, -0.00930733913, 4.731582e-5, -9.054e-8)

# DOTS polynomial coefficients
_DOTS_MEN = (-307.75076, 24.0900756, -0.1918759221, 0.0007391293, -1.093e-6)
_DOTS_WOMEN = (-57.96288, 13.6175032, -0.1126655495, 0.0005158568, -7.12e-7)


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
    if score >= 500: return "Elite"
    if score >= 400: return "Master"
    if score >= 300: return "Advanced"
    if score >= 200: return "Intermediate"
    return "Beginner"


def register(mcp: Any, audit: Callable) -> None:

    @mcp.tool()
    def pl_calculate_wilks(bodyweight_kg: float, total_kg: float, sex: str = "m") -> str:
        """Wilks 2020 score. sex: 'm' or 'f'."""
        audit("pl_calculate_wilks", {"bodyweight_kg": bodyweight_kg, "total_kg": total_kg, "sex": sex})
        score = _wilks(total_kg, bodyweight_kg, sex)
        return json.dumps({
            "bodyweight_kg": bodyweight_kg,
            "total_kg": total_kg,
            "sex": sex,
            "wilks_score": score,
            "classification": _classify(score),
        }, indent=2)

    @mcp.tool()
    def pl_calculate_dots(bodyweight_kg: float, total_kg: float, sex: str = "m") -> str:
        """DOTS score. sex: 'm' or 'f'."""
        audit("pl_calculate_dots", {"bodyweight_kg": bodyweight_kg, "total_kg": total_kg, "sex": sex})
        score = _dots(total_kg, bodyweight_kg, sex)
        return json.dumps({
            "bodyweight_kg": bodyweight_kg,
            "total_kg": total_kg,
            "sex": sex,
            "dots_score": score,
            "classification": _classify(score),
        }, indent=2)

    @mcp.tool()
    def pl_predict_attempts(squat_kg: float, bench_kg: float, deadlift_kg: float) -> str:
        """Suggest opener, 2nd, and 3rd attempts for a powerlifting meet."""
        audit("pl_predict_attempts", {"squat_kg": squat_kg, "bench_kg": bench_kg, "deadlift_kg": deadlift_kg})
        result: dict = {}
        for lift, kg in (("squat", squat_kg), ("bench", bench_kg), ("deadlift", deadlift_kg)):
            result[lift] = {
                "opener":    round(kg * 0.90 / 2.5) * 2.5,
                "second":    round(kg * 0.97 / 2.5) * 2.5,
                "third_pr":  round(kg * 1.01 / 2.5) * 2.5,
                "third_big": round(kg * 1.04 / 2.5) * 2.5,
            }
        result["projected_total_kg"] = sum(result[l]["third_pr"] for l in ("squat", "bench", "deadlift"))
        return json.dumps(result, indent=2)

    @mcp.tool()
    def pl_analyze_sbd_ratio(squat_kg: float, bench_kg: float, deadlift_kg: float) -> str:
        """Identify weakest lift vs. elite squat:bench:deadlift proportions (raw)."""
        audit("pl_analyze_sbd_ratio", {"squat_kg": squat_kg, "bench_kg": bench_kg, "deadlift_kg": deadlift_kg})
        total = squat_kg + bench_kg + deadlift_kg
        ratios = {
            "squat":    round(squat_kg / total * 100, 1),
            "bench":    round(bench_kg / total * 100, 1),
            "deadlift": round(deadlift_kg / total * 100, 1),
        }
        # Elite raw powerlifting averages: S~37%, B~26%, D~37%
        elite = {"squat": 37.0, "bench": 26.0, "deadlift": 37.0}
        deviations = {k: round(ratios[k] - elite[k], 1) for k in elite}
        weakest = min(deviations, key=deviations.get)
        return json.dumps({
            "squat_kg": squat_kg, "bench_kg": bench_kg, "deadlift_kg": deadlift_kg,
            "total_kg": total,
            "ratios_pct": ratios,
            "deviation_from_elite_avg": deviations,
            "weakest_lift": weakest,
            "recommendation": (
                f"Focus additional volume on {weakest} — "
                f"it is {abs(deviations[weakest])}% below elite proportion."
            ),
        }, indent=2)
