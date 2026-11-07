from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from robo_trainer import planner
from robo_trainer.db import get_conn, init_db
from robo_trainer.exercises import KNOWN_LIMITATIONS


def _today() -> date:
    return datetime.now().date()


def _err(message: str) -> str:
    return json.dumps({"error": message})


def _load(table: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(f"SELECT data FROM {table} WHERE id=1").fetchone()
    return json.loads(row["data"]) if row else None


def _save(table: str, data: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO {table} (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=datetime('now')",
            (json.dumps(data),),
        )


def register(mcp: Any, audit: Callable) -> None:
    init_db()

    @mcp.tool()
    def profile_set(
        goals: list[str] | None = None,
        experience: str | None = None,
        equipment: list[str] | None = None,
        days_per_week: int | None = None,
        session_minutes: int | None = None,
        injuries: list[str] | None = None,
    ) -> str:
        """Save your fitness profile: goals, experience, equipment, days per week, session length, limitation tags. Fields you leave out keep their stored value."""
        audit("profile_set", {
            "goals": goals, "experience": experience, "equipment": equipment, "days_per_week": days_per_week,
            "session_minutes": session_minutes, "injuries": injuries,
        })
        try:
            update = planner.clean_profile_update(goals, experience, equipment, days_per_week, session_minutes, injuries)
        except planner.PlanError as e:
            return _err(str(e))
        if not update:
            return _err("Nothing to save. Pass at least one profile field.")
        profile = {**(_load("user_profile") or {}), **update}
        _save("user_profile", profile)
        return json.dumps({"saved": True, "profile": profile, "missing_fields": planner.missing_fields(profile)}, indent=2)

    @mcp.tool()
    def profile_get() -> str:
        """Return the stored fitness profile, or list the fields still missing before a plan can be made."""
        audit("profile_get", {})
        profile = _load("user_profile") or {}
        missing = planner.missing_fields(profile)
        return json.dumps({"profile": profile, "complete": not missing, "missing_fields": missing}, indent=2)

    @mcp.tool()
    def exercise_search(
        muscle: str = "",
        equipment: list[str] | None = None,
        exclude_limitations: list[str] | None = None,
        pattern: str = "",
        max_difficulty: str = "",
        limit: int = 20,
    ) -> str:
        """Search the built-in exercise library by muscle group, owned equipment and limitation tags to leave out. Only filters by tag, not medical advice."""
        audit("exercise_search", {"muscle": muscle, "equipment": equipment, "exclude_limitations": exclude_limitations, "pattern": pattern})
        try:
            found = planner.search_exercises(muscle, equipment, exclude_limitations, pattern, max_difficulty, limit)
        except planner.PlanError as e:
            return _err(str(e))
        return json.dumps({
            "count": len(found),
            "exercises": [e.as_dict() for e in found],
            "known_limitation_tags": list(KNOWN_LIMITATIONS),
            "note": "A limitation filter only removes exercises tagged with that limitation. Ask a qualified professional about any injury.",
        }, indent=2)

    @mcp.tool()
    def plan_generate(weeks: int = 4, start_date: str = "") -> str:
        """Build a multi-week program from the stored profile with sets, reps, RPE, a deload week and the rules used. Replaces any stored plan."""
        audit("plan_generate", {"weeks": weeks, "start_date": start_date})
        try:
            profile = _load("user_profile") or {}
            start = planner.parse_date(start_date, "start_date") if start_date else _today()
            plan = planner.generate_plan(profile, weeks, start)
        except planner.PlanError as e:
            return _err(str(e))
        replaced = _load("training_plan") is not None
        _save("training_plan", plan)
        return json.dumps({"replaced_existing_plan": replaced, **plan})

    @mcp.tool()
    def plan_get_today(date: str = "") -> str:
        """Return the planned session for a date (defaults to today), or say it is a rest day."""
        audit("plan_get_today", {"date": date})
        try:
            day = planner.parse_date(date) if date else _today()
        except planner.PlanError as e:
            return _err(str(e))
        plan = _load("training_plan")
        if plan is None:
            return json.dumps({"date": day.isoformat(), "status": "no_plan", "note": "No plan stored. Use plan_generate."})
        found = planner.session_on(plan, day)
        if found:
            week, session = found
            return json.dumps({
                "date": day.isoformat(), "status": "training_day", "week": week["week"], "phase": week["phase"],
                "session": session, "notice": planner.NOTICE,
            }, indent=2)
        status = "rest_day" if plan["start_date"] <= day.isoformat() <= plan["end_date"] else "outside_plan"
        upcoming = sorted(s["date"] for _, s in planner.iter_sessions(plan) if s["date"] > day.isoformat())
        return json.dumps({
            "date": day.isoformat(), "status": status, "next_session_date": upcoming[0] if upcoming else None,
            "plan_range": [plan["start_date"], plan["end_date"]],
        }, indent=2)

    @mcp.tool()
    def plan_adjust(
        reason: str,
        from_date: str = "",
        days_missed: int = 0,
        equipment: list[str] | None = None,
        limitation: str = "",
    ) -> str:
        """Revise the stored plan for low_readiness, missed_days, equipment_change or injury and return the revised plan plus a diff."""
        audit("plan_adjust", {"reason": reason, "from_date": from_date, "days_missed": days_missed, "equipment": equipment, "limitation": limitation})
        if reason not in planner.REASONS:
            return _err(f"reason must be one of: {', '.join(planner.REASONS)}.")
        plan = _load("training_plan")
        if plan is None:
            return _err("No plan stored. Use plan_generate first.")
        try:
            start = planner.parse_date(from_date, "from_date") if from_date else _today()
            profile = dict(plan["profile"])
            if reason == "missed_days":
                planner._num(days_missed=(days_missed, 1, 28, True))
            elif reason == "equipment_change":
                if not equipment:
                    return _err("equipment_change needs the new equipment list, for example [\"dumbbells\", \"bench\"].")
                profile["equipment"] = planner.clean_equipment(equipment)
            elif reason == "injury":
                tags = planner.clean_injuries([t for t in limitation.split(",") if t.strip()]) if limitation else []
                if not tags:
                    return _err("injury needs a limitation tag, for example \"knee\".")
                profile["injuries"] = list(dict.fromkeys([*profile.get("injuries", []), *tags]))
            revised, rules = planner.adjust_plan(plan, reason, start, days_missed, profile)
        except planner.PlanError as e:
            return _err(str(e))
        changes = planner.diff_plans(plan, revised)
        _save("training_plan", revised)
        if reason in ("equipment_change", "injury"):
            _save("user_profile", {**(_load("user_profile") or {}), "equipment": profile["equipment"], "injuries": profile.get("injuries", [])})
        return json.dumps({
            "reason": reason, "from_date": start.isoformat(), "rules_applied": rules,
            "summary": dict(Counter(c["field"] for c in changes)), "changes": changes, "revised_plan": revised,
        })

    @mcp.tool()
    def plan_review_progress(weeks: int = 4, as_of: str = "") -> str:
        """Compare planned sessions with logged sets over the last N weeks, with sleep, stress and overreaching context from existing logs."""
        audit("plan_review_progress", {"weeks": weeks, "as_of": as_of})
        try:
            planner._num(weeks=(weeks, 1, 12, True))
            end = planner.parse_date(as_of, "as_of") if as_of else _today()
        except planner.PlanError as e:
            return _err(str(e))
        plan = _load("training_plan")
        if plan is None:
            return _err("No plan stored. Use plan_generate first.")
        first = end - timedelta(days=7 * weeks - 1)
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT date, exercise, weight_kg, reps, rpe FROM training_log WHERE date BETWEEN ? AND ? ORDER BY date, id",
                (first.isoformat(), end.isoformat()),
            ).fetchall()]
            sleep = conn.execute(
                "SELECT COUNT(*) n, AVG(hours) hours, AVG(quality) quality FROM sleep_log WHERE date BETWEEN ? AND ?",
                (first.isoformat(), end.isoformat()),
            ).fetchone()
            mood = conn.execute(
                "SELECT COUNT(*) n, AVG(stress) stress FROM mood_log WHERE date BETWEEN ? AND ?",
                (first.isoformat(), end.isoformat()),
            ).fetchone()
        result = planner.review(plan, rows, end, weeks)
        result["recovery_context"] = {
            "sleep_days_logged": sleep["n"],
            "avg_sleep_hours": round(sleep["hours"], 1) if sleep["n"] else None,
            "avg_sleep_quality": round(sleep["quality"], 1) if sleep["n"] else None,
            "mood_days_logged": mood["n"],
            "avg_stress": round(mood["stress"], 1) if mood["n"] else None,
        }
        result["overreaching"] = planner.overreaching_signal(rows, end)
        result["notes"] = [
            "Logged sets are matched to planned exercises by name (case and punctuation ignored). Sets logged under a different name show as different_work.",
            "Cardio and mobility sessions are not loggable with training_log_set, so they are listed as not_loggable and left out of the counts.",
            planner.NOTICE,
        ]
        return json.dumps(result, indent=2)
