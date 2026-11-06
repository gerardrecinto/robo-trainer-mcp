"""Pure fitness formulas with no database or network, so the website can run them in the browser."""
from __future__ import annotations


def epley_1rm(weight: float, reps: int) -> float:
    if reps == 1:
        return weight
    return round(weight * (1 + reps / 30.0), 1)


def brzycki_1rm(weight: float, reps: int) -> float:
    if reps == 1:
        return weight
    return round(weight * 36.0 / (37.0 - reps), 1)


# Approximate %1RM when a set is taken to failure, by reps to failure. This is the widely used
# RPE chart (Tuchscherer). It is an average from lifters, so treat results as estimates.
PERCENT_BY_REPS_TO_FAILURE = {
    1: 100.0, 2: 95.5, 3: 92.2, 4: 89.2, 5: 86.3, 6: 83.7,
    7: 81.1, 8: 78.6, 9: 76.2, 10: 73.9, 11: 70.7, 12: 68.0,
}


def percent_for_reps_to_failure(reps_to_failure: float) -> float:
    low = int(reps_to_failure)
    high = min(low + 1, 12)
    if low >= 12:
        return PERCENT_BY_REPS_TO_FAILURE[12]
    frac = reps_to_failure - low
    a, b = PERCENT_BY_REPS_TO_FAILURE[low], PERCENT_BY_REPS_TO_FAILURE[high]
    return a + (b - a) * frac


ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "very": 1.725, "extra": 1.9}
PROTEIN_G_PER_KG = {"lose": 2.0, "maintain": 1.6, "gain": 1.8}


def estimate_targets(weight_kg: float, height_cm: float, age: int, sex: str, activity: str, goal: str) -> dict:
    """Mifflin-St Jeor energy estimate with evidence-based protein and fat floors.

    Protein: about 1.6 g/kg supports muscle gain in most people (Morton et al., 2018). The ISSN
    position stand gives 1.4 to 2.0 g/kg, and the high end helps keep muscle in a calorie deficit.
    Fat stays at or above 0.6 g/kg and 25 percent of calories. Fiber is about 14 g per 1000 kcal.
    """
    sex_key = sex.strip().lower()
    if sex_key not in ("m", "male", "f", "female"):
        return {"error": "sex must be 'male' or 'female' (it is used by the Mifflin-St Jeor equation)."}
    if activity not in ACTIVITY:
        return {"error": f"activity must be one of: {', '.join(ACTIVITY)}."}
    if goal not in PROTEIN_G_PER_KG:
        return {"error": "goal must be one of: lose, maintain, gain."}
    male = sex_key in ("m", "male")
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if male else -161)
    tdee = bmr * ACTIVITY[activity]
    notes: list[str] = []
    if goal == "lose":
        # Moderate deficit: 20 percent, capped at roughly 1 percent of bodyweight lost per week.
        max_deficit = 11.0 * weight_kg
        deficit = min(tdee * 0.20, max_deficit)
        calories = tdee - deficit
        floor = 1500.0 if male else 1200.0
        if calories < floor:
            calories = floor
            notes.append(f"Calories were raised to {int(floor)}, a common safe minimum without medical supervision.")
    elif goal == "gain":
        calories = tdee * 1.10
    else:
        calories = tdee
    protein_g = PROTEIN_G_PER_KG[goal] * weight_kg
    fat_g = max(0.6 * weight_kg, 0.25 * calories / 9.0)
    carbs_g = max((calories - protein_g * 4 - fat_g * 9) / 4.0, 0.0)
    return {
        "inputs": {"weight_kg": weight_kg, "height_cm": height_cm, "age": age, "sex": sex_key, "activity": activity, "goal": goal},
        "bmr_kcal": round(bmr),
        "maintenance_kcal": round(tdee),
        "targets": {
            "calories": round(calories),
            "protein_g": round(protein_g),
            "carbs_g": round(carbs_g),
            "fat_g": round(fat_g),
            "fiber_g": round(14 * calories / 1000),
        },
        "notes": notes + [
            "These are estimates. Weigh yourself weekly, then adjust calories by about 100 to 200 if your trend is off.",
            "Not medical advice. If you are pregnant, have a history of disordered eating, or have a medical condition, plan with a clinician.",
        ],
        "method": "Mifflin-St Jeor equation, activity multipliers 1.2 to 1.9, protein 1.6 to 2.0 g/kg.",
    }
