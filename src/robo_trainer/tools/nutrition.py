from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable

from robo_trainer.db import get_conn, init_db


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
            return json.dumps(_demo_food_search(query), indent=2)

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
        avg = {k: round(sum(w[k] for w in weekly) / 7, 1) for k in ("calories", "protein_g", "carbs_g", "fat_g")}
        return json.dumps({"days": weekly, "7_day_avg": avg, "goal": dict(goal)}, indent=2)

    @mcp.tool()
    def nutrition_set_goals(calories: float, protein_g: float, carbs_g: float, fat_g: float) -> str:
        """Set your daily calorie and macro targets."""
        audit("nutrition_set_goals", {"calories": calories})
        with get_conn() as conn:
            conn.execute(
                "UPDATE nutrition_goals SET calories=?, protein_g=?, carbs_g=?, fat_g=?, "
                "updated_at=datetime('now') WHERE id=1",
                (calories, protein_g, carbs_g, fat_g),
            )
        return json.dumps({"updated": True, "goals": {
            "calories": calories, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g
        }})


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
