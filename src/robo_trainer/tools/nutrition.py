from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from robo_trainer.db import get_conn, init_db
from robo_trainer.validation import check, sample


def register(mcp: Any, audit: Callable) -> None:
    init_db()

    @mcp.tool()
    def nutrition_search_food(query: str, limit: int = 5) -> str:
        """Search Open Food Facts (3M+ products) for nutrition info."""
        audit("nutrition_search_food", {"query": query})
        try:
            import requests
            resp = requests.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={
                    "search_terms": query,
                    "json": 1,
                    "page_size": limit,
                    "fields": "product_name,nutriments,serving_size",
                },
                timeout=5,
            )
            resp.raise_for_status()
            products = resp.json().get("products", [])
            results = []
            for p in products:
                n = p.get("nutriments", {})
                results.append({
                    "name": p.get("product_name", "Unknown"),
                    "serving_size": p.get("serving_size", "100g"),
                    "per_100g": {
                        "calories": n.get("energy-kcal_100g", 0),
                        "protein_g": n.get("proteins_100g", 0),
                        "carbs_g": n.get("carbohydrates_100g", 0),
                        "fat_g": n.get("fat_100g", 0),
                    },
                })
            return json.dumps(results, indent=2)
        except Exception:
            return sample(_demo_food_search(query), "Could not reach Open Food Facts, so these are made-up sample values, not real foods.")

    @mcp.tool()
    def nutrition_log_meal(
        food_name: str,
        grams: float,
        calories: float,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        meal_type: str = "other",
        date: str = "",
    ) -> str:
        """Log a meal to your food diary."""
        audit("nutrition_log_meal", {"food_name": food_name, "grams": grams})
        err = check(
            grams=(grams, 0, 10000), calories=(calories, 0, 10000), protein_g=(protein_g, 0, 1000),
            carbs_g=(carbs_g, 0, 2000), fat_g=(fat_g, 0, 1000),
        )
        if err:
            return err
        d = date or datetime.now().strftime("%Y-%m-%d")
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO food_log (date, meal_type, food_name, grams, calories, protein_g, carbs_g, fat_g) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (d, meal_type, food_name, grams, calories, protein_g, carbs_g, fat_g),
            )
        return json.dumps({"logged": food_name, "date": d, "calories": calories, "protein_g": protein_g})

    @mcp.tool()
    def nutrition_get_daily_summary(date: str = "") -> str:
        """Get macro totals for a day vs. your goals."""
        audit("nutrition_get_daily_summary", {"date": date})
        d = date or datetime.now().strftime("%Y-%m-%d")
        with get_conn() as conn:
            row = conn.execute(
                "SELECT SUM(calories) cal, SUM(protein_g) prot, SUM(carbs_g) carbs, SUM(fat_g) fat "
                "FROM food_log WHERE date=?",
                (d,),
            ).fetchone()
            goal = conn.execute("SELECT * FROM nutrition_goals WHERE id=1").fetchone()
        actual = {
            "calories": row["cal"] or 0,
            "protein_g": row["prot"] or 0,
            "carbs_g": row["carbs"] or 0,
            "fat_g": row["fat"] or 0,
        }
        target = {
            "calories": goal["calories"],
            "protein_g": goal["protein_g"],
            "carbs_g": goal["carbs_g"],
            "fat_g": goal["fat_g"],
        }
        return json.dumps({
            "date": d,
            "actual": actual,
            "target": target,
            "remaining": {k: round(target[k] - actual[k], 1) for k in target},
        }, indent=2)

    @mcp.tool()
    def nutrition_get_weekly_macros() -> str:
        """7-day rolling macro averages vs. goals."""
        audit("nutrition_get_weekly_macros", {})
        today = datetime.now().date()
        days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT date, SUM(calories) cal, SUM(protein_g) prot, SUM(carbs_g) carbs, SUM(fat_g) fat "
                "FROM food_log WHERE date >= ? GROUP BY date",
                (days[0],),
            ).fetchall()
            goal = conn.execute("SELECT * FROM nutrition_goals WHERE id=1").fetchone()
        data = {
            r["date"]: {"calories": r["cal"], "protein_g": r["prot"], "carbs_g": r["carbs"], "fat_g": r["fat"]}
            for r in rows
        }
        weekly = [
            {"date": d, **data.get(d, {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0})}
            for d in days
        ]
        logged = [w for w in weekly if w["date"] in data]
        avg = {
            k: round(sum(w[k] for w in logged) / len(logged), 1) if logged else 0
            for k in ("calories", "protein_g", "carbs_g", "fat_g")
        }
        return json.dumps({
            "days": weekly,
            "days_logged": len(logged),
            "7_day_avg": avg,
            "note": "Averages cover only the days you logged food, so a day you skipped does not count as zero.",
            "goal": dict(goal),
        }, indent=2)

    @mcp.tool()
    def nutrition_estimate_targets(
        weight_kg: float,
        height_cm: float,
        age: int,
        sex: str,
        activity: str = "moderate",
        goal: str = "maintain",
    ) -> str:
        """Estimate daily calories and macros. activity: sedentary, light, moderate, very, extra. goal: lose, maintain, gain."""
        audit("nutrition_estimate_targets", {"weight_kg": weight_kg, "goal": goal, "activity": activity})
        err = check(weight_kg=(weight_kg, 30, 300), height_cm=(height_cm, 100, 250), age=(age, 18, 100, True))
        if err:
            return err
        result = estimate_targets(weight_kg, height_cm, age, sex, activity, goal)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def nutrition_set_goals(calories: float, protein_g: float, carbs_g: float, fat_g: float) -> str:
        """Set your daily calorie and macro targets."""
        audit("nutrition_set_goals", {"calories": calories})
        err = check(calories=(calories, 800, 10000), protein_g=(protein_g, 0, 600), carbs_g=(carbs_g, 0, 1500), fat_g=(fat_g, 0, 500))
        if err:
            return err
        with get_conn() as conn:
            conn.execute(
                "UPDATE nutrition_goals SET calories=?, protein_g=?, carbs_g=?, fat_g=?, "
                "updated_at=datetime('now') WHERE id=1",
                (calories, protein_g, carbs_g, fat_g),
            )
        return json.dumps({"updated": True, "goals": {
            "calories": calories, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g
        }})


_ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "very": 1.725, "extra": 1.9}
_PROTEIN_G_PER_KG = {"lose": 2.0, "maintain": 1.6, "gain": 1.8}


def estimate_targets(weight_kg: float, height_cm: float, age: int, sex: str, activity: str, goal: str) -> dict:
    """Mifflin-St Jeor energy estimate with evidence-based protein and fat floors.

    Protein: about 1.6 g/kg supports muscle gain in most people (Morton et al., 2018). The ISSN
    position stand gives 1.4 to 2.0 g/kg, and the high end helps keep muscle in a calorie deficit.
    Fat stays at or above 0.6 g/kg and 25 percent of calories. Fiber is about 14 g per 1000 kcal.
    """
    sex_key = sex.strip().lower()
    if sex_key not in ("m", "male", "f", "female"):
        return {"error": "sex must be 'male' or 'female' (it is used by the Mifflin-St Jeor equation)."}
    if activity not in _ACTIVITY:
        return {"error": f"activity must be one of: {', '.join(_ACTIVITY)}."}
    if goal not in _PROTEIN_G_PER_KG:
        return {"error": "goal must be one of: lose, maintain, gain."}
    male = sex_key in ("m", "male")
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if male else -161)
    tdee = bmr * _ACTIVITY[activity]
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
    protein_g = _PROTEIN_G_PER_KG[goal] * weight_kg
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


def _demo_food_search(query: str) -> list[dict]:
    return [
        {
            "name": f"{query.title()} (generic)",
            "serving_size": "100g",
            "per_100g": {"calories": 165, "protein_g": 31.0, "carbs_g": 0.0, "fat_g": 3.6},
        },
        {
            "name": f"{query.title()} (cooked)",
            "serving_size": "150g",
            "per_100g": {"calories": 172, "protein_g": 29.5, "carbs_g": 0.0, "fat_g": 4.1},
        },
    ]
