"""Rule-based program planner. No network, no randomness: the same profile and start date give the same plan.

Nothing here is medical advice. The limitation filter only removes exercises that carry a matching tag.
"""
from __future__ import annotations

import copy
import json
import re
from collections import Counter
from datetime import date, timedelta
from typing import Any

from robo_trainer.exercises import (
    BY_NAME,
    COMPOUND_PATTERNS,
    DIFFICULTIES,
    EQUIPMENT,
    KNOWN_LIMITATIONS,
    LIBRARY,
    Exercise,
    available,
    normalize_limitation,
)
from robo_trainer.validation import check

GOALS = ("strength", "hypertrophy", "fat_loss", "endurance", "mobility", "general_health")
EXPERIENCE = DIFFICULTIES
REASONS = ("low_readiness", "missed_days", "equipment_change", "injury")
REQUIRED_PROFILE_FIELDS = ("goals", "experience", "equipment", "days_per_week", "session_minutes")
NOTICE = (
    "General fitness information, not medical advice. The limitation filter only removes exercises tagged "
    "for the limitations you listed. Ask a qualified professional about any injury or health condition."
)

WARMUP_MINUTES = 5
FINISHER_MINUTES = 10
SET_MINUTES = {"reps": 0.75, "seconds": 1.0}
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_OFFSETS = {1: (0,), 2: (0, 3), 3: (0, 2, 4), 4: (0, 1, 3, 4), 5: (0, 1, 2, 4, 5), 6: (0, 1, 2, 3, 4, 5), 7: (0, 1, 2, 3, 4, 5, 6)}
# Same thresholds as training_check_overreaching.
VOLUME_RISE = 1.05
RPE_RISE = 0.5

# goal -> compound sets, compound reps, accessory sets, accessory reps, starting RPE, compound rest minutes
PRESCRIPTION = {
    "strength": (4, (3, 5), 3, (8, 12), 7.0, 2.5),
    "hypertrophy": (3, (6, 10), 3, (10, 15), 7.0, 1.5),
    "fat_loss": (3, (8, 12), 3, (12, 15), 7.0, 1.5),
    "endurance": (3, (10, 15), 2, (12, 20), 6.0, 1.0),
    "mobility": (2, (8, 12), 2, (10, 15), 6.0, 1.0),
    "general_health": (3, (8, 12), 2, (10, 15), 6.5, 1.5),
}
RPE_CAP = {"beginner": 8.0, "intermediate": 8.5, "advanced": 9.0}
SET_CAP = {"beginner": 3, "intermediate": 4, "advanced": 5}

TEMPLATES = {
    "full_a": ["squat", "horizontal_push", "horizontal_pull", "hinge", "core"],
    "full_b": ["lunge", "vertical_push", "vertical_pull", "hinge", "core"],
    "full_c": ["squat", "horizontal_push", "vertical_pull", "lunge", "core"],
    "upper": ["horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull", "arms_biceps", "arms_triceps"],
    "lower": ["squat", "hinge", "lunge", "calves", "core"],
    "push": ["horizontal_push", "vertical_push", "shoulders_iso", "arms_triceps"],
    "pull": ["vertical_pull", "horizontal_pull", "arms_biceps", "shoulders_iso"],
    "legs": ["squat", "hinge", "lunge", "calves", "core"],
    "cardio": ["cardio"],
    "mobility": ["mobility"] * 5,
}


class PlanError(ValueError):
    """A message that is safe to hand straight back to the caller."""


def _num(**fields: tuple) -> None:
    err = check(**fields)
    if err:
        raise PlanError(json.loads(err)["error"])


def parse_date(text: str, name: str = "date") -> date:
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise PlanError(f"{name} must look like YYYY-MM-DD.")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise PlanError(f"{name} is not a real calendar date.") from None


# ---------- profile ----------

def clean_equipment(items: Any) -> list[str]:
    if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
        raise PlanError("equipment must be a list of names.")
    cleaned = list(dict.fromkeys("_".join(i.strip().lower().split()) for i in items if i.strip()))
    unknown = [i for i in cleaned if i not in EQUIPMENT]
    if unknown:
        raise PlanError(f"Unknown equipment: {', '.join(unknown)}. Choose from: {', '.join(EQUIPMENT)}.")
    return cleaned


def clean_injuries(items: Any) -> list[str]:
    if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
        raise PlanError("injuries must be a list of short text tags, for example [\"knee\"].")
    cleaned = list(dict.fromkeys(normalize_limitation(i) for i in items if i.strip()))
    if len(cleaned) > 10:
        raise PlanError("injuries can hold at most 10 tags.")
    if any(len(t) > 40 for t in cleaned):
        raise PlanError("Each injury tag must be 40 characters or fewer.")
    return cleaned


def clean_profile_update(
    goals: Any = None, experience: Any = None, equipment: Any = None, days_per_week: Any = None,
    session_minutes: Any = None, injuries: Any = None,
) -> dict:
    """Validate the fields that were supplied. Fields left as None are not part of the update."""
    out: dict = {}
    if goals is not None:
        if not isinstance(goals, list) or not goals or not all(isinstance(g, str) for g in goals):
            raise PlanError(f"goals must be a non-empty list. Choose from: {', '.join(GOALS)}.")
        cleaned = list(dict.fromkeys(g.strip().lower() for g in goals))
        bad = [g for g in cleaned if g not in GOALS]
        if bad:
            raise PlanError(f"Unknown goal: {', '.join(bad)}. Choose from: {', '.join(GOALS)}.")
        if len(cleaned) > 3:
            raise PlanError("Pick at most 3 goals. The first one drives the split.")
        out["goals"] = cleaned
    if experience is not None:
        level = experience.strip().lower() if isinstance(experience, str) else experience
        if level not in EXPERIENCE:
            raise PlanError(f"experience must be one of: {', '.join(EXPERIENCE)}.")
        out["experience"] = level
    if equipment is not None:
        out["equipment"] = clean_equipment(equipment)
    if days_per_week is not None:
        _num(days_per_week=(days_per_week, 1, 7, True))
        out["days_per_week"] = int(days_per_week)
    if session_minutes is not None:
        _num(session_minutes=(session_minutes, 15, 180, True))
        out["session_minutes"] = int(session_minutes)
    if injuries is not None:
        out["injuries"] = clean_injuries(injuries)
    return out


def missing_fields(profile: dict) -> list[str]:
    return [f for f in REQUIRED_PROFILE_FIELDS if f not in profile]


# ---------- exercise selection ----------

def search_exercises(
    muscle: str = "", equipment: list[str] | None = None, exclude_limitations: list[str] | None = None,
    pattern: str = "", max_difficulty: str = "", limit: int = 20,
) -> list[Exercise]:
    excluded = set(clean_injuries(exclude_limitations or []))
    owned = set(clean_equipment(equipment)) if equipment is not None else set(EQUIPMENT)
    level = max_difficulty.strip().lower() if max_difficulty else DIFFICULTIES[-1]
    if level not in DIFFICULTIES:
        raise PlanError(f"max_difficulty must be one of: {', '.join(DIFFICULTIES)}.")
    muscles = {m for e in LIBRARY for m in e.muscles}
    muscle = muscle.strip().lower()
    if muscle and muscle not in muscles:
        raise PlanError(f"Unknown muscle group: {muscle}. Choose from: {', '.join(sorted(muscles))}.")
    pattern = pattern.strip().lower()
    if pattern and pattern not in {e.pattern for e in LIBRARY}:
        raise PlanError(f"Unknown pattern: {pattern}. Choose from: {', '.join(dict.fromkeys(e.pattern for e in LIBRARY))}.")
    _num(limit=(limit, 1, 100, True))
    found = [
        e for e in LIBRARY
        if (not muscle or muscle in e.muscles) and (not pattern or e.pattern == pattern)
        and available(e, owned, excluded, level)
    ]
    return found[:limit]


def _pick(pattern: str, ctx: dict, variant: int, used: set[str]) -> Exercise | None:
    level = ctx["experience"]
    pool = [e for e in LIBRARY if e.pattern == pattern and e.name not in used and available(e, ctx["equipment"], ctx["excluded"], level)]
    # Hardest allowed first, library order breaks ties. Variant rotates the choice so repeated sessions differ.
    pool.sort(key=lambda e: -DIFFICULTIES.index(e.difficulty))
    return pool[variant % len(pool)] if pool else None


def _alternatives(ex: Exercise, ctx: dict) -> list[str]:
    return [a for a in ex.alternatives if a in BY_NAME and available(BY_NAME[a], ctx["equipment"], ctx["excluded"], ctx["experience"])]


# ---------- prescription ----------

def _base_slot(ex: Exercise, ctx: dict) -> dict:
    sets_c, reps_c, sets_i, reps_i, rpe, rest_c = PRESCRIPTION[ctx["goal"]]
    experience = ctx["experience"]
    slot = {"slot": ex.pattern, "exercise": ex.name, "unit": ex.unit, "alternatives": _alternatives(ex, ctx)}
    if ex.unit == "minutes":
        slot.update(sets=1, lo=0, hi=0, minutes=0, rpe=None, rest=0.0)
        return slot
    start_rpe = max(5.0, rpe - 1) if experience == "beginner" else rpe
    if ex.unit == "seconds":
        slot.update(sets=2, lo=30, hi=60, rpe=None, rest=0.5)
    elif ex.compound:
        sets = min(sets_c, SET_CAP[experience]) if experience == "beginner" else sets_c
        slot.update(sets=sets, lo=reps_c[0], hi=reps_c[1], rpe=start_rpe, rest=rest_c)
    else:
        slot.update(sets=sets_i, lo=reps_i[0], hi=reps_i[1], rpe=start_rpe, rest=1.0)
    return slot


def _cost(slot: dict) -> float:
    if slot["unit"] == "minutes":
        return float(slot["minutes"])
    return slot["sets"] * (SET_MINUTES[slot["unit"]] + slot["rest"])


def _estimate(slots: list[dict]) -> float:
    warmup = WARMUP_MINUTES if any(s["slot"] in COMPOUND_PATTERNS for s in slots) else 0
    return warmup + sum(_cost(s) for s in slots)


def _fit(slots: list[dict], budget: int, ctx: dict) -> list[str]:
    """Trim or grow a session toward the time budget. Returns notes about what changed."""
    notes: list[str] = []
    while _estimate(slots) > budget and len(slots) > 3:
        dropped = slots.pop()
        notes.append(f"dropped {dropped['exercise']} to fit {budget} minutes")
    while _estimate(slots) > budget:
        trimmable = [s for s in slots if s["unit"] != "minutes" and s["sets"] > 2]
        if not trimmable:
            break
        for s in trimmable:
            s["sets"] -= 1
        notes.append("removed one set from each exercise to fit the time")
    while _estimate(slots) > budget and len(slots) > 2:
        dropped = slots.pop()
        notes.append(f"dropped {dropped['exercise']} to fit {budget} minutes")
    if _estimate(slots) > budget:
        notes.append(f"could not fit {budget} minutes: this session is estimated at {round(_estimate(slots))}")
    cap = SET_CAP[ctx["experience"]]
    while True:
        growable = [s for s in slots if s["unit"] == "reps" and s["slot"] in COMPOUND_PATTERNS and s["sets"] < cap]
        if not growable:
            break
        target = min(growable, key=lambda s: s["sets"])
        if _estimate(slots) + SET_MINUTES["reps"] + target["rest"] > budget:
            break
        target["sets"] += 1
    return notes


def _build_slots(template: str, variant: int, ctx: dict, finisher: bool) -> tuple[list[dict], list[str]]:
    slots: list[dict] = []
    warnings: list[str] = []
    used: set[str] = set()
    for pattern in TEMPLATES[template]:
        ex = _pick(pattern, ctx, variant, used)
        if ex is None:
            warnings.append(f"{template}: no {pattern} exercise fits your equipment, level and limitations, so that slot was skipped")
            continue
        used.add(ex.name)
        slots.append(_base_slot(ex, ctx))
    if finisher:
        ex = _pick("cardio", ctx, variant, used)
        if ex is not None:
            slot = _base_slot(ex, ctx)
            slot["minutes"] = slot["max_minutes"] = FINISHER_MINUTES
            slots.append(slot)
    for slot in slots:
        if slot["unit"] == "minutes" and not slot["minutes"]:
            slot["minutes"] = max(10, min(round(ctx["minutes"] * 0.8), 60))
            slot["max_minutes"] = max(10, min(ctx["minutes"], 60))
    return slots, warnings


def choose_split(days: int, goal: str) -> tuple[str, list[str]]:
    if goal in ("endurance", "mobility"):
        other = "cardio" if goal == "endurance" else "mobility"
        if days == 1:
            return f"{other}_only", [other]
        n_other = days // 2
        strength = [f"full_{'abc'[i % 3]}" for i in range(days - n_other)]
        sessions: list[str] = []
        for i in range(days):
            sessions.append(strength.pop(0) if (i % 2 == 0 and strength) or n_other == 0 else other)
            if sessions[-1] == other:
                n_other -= 1
        return f"strength_plus_{other}", sessions
    table = {
        1: ("full_body", ["full_a"]),
        2: ("full_body", ["full_a", "full_b"]),
        3: ("full_body", ["full_a", "full_b", "full_c"]),
        4: ("upper_lower", ["upper", "lower", "upper", "lower"]),
        5: ("push_pull_legs_plus_upper_lower", ["push", "pull", "legs", "upper", "lower"]),
        6: ("push_pull_legs", ["push", "pull", "legs", "push", "pull", "legs"]),
        7: ("push_pull_legs_plus_mobility", ["push", "pull", "legs", "push", "pull", "legs", "mobility"]),
    }
    return table[days]


def _week_slot(slot: dict, c: int, deload: bool, experience: str) -> dict:
    out = {k: slot[k] for k in ("slot", "exercise", "unit", "alternatives")}
    sets = slot["sets"]
    if slot["unit"] == "minutes":
        minutes = slot["minutes"]
        minutes = round(minutes * 0.7) if deload else min(round(minutes * (1 + 0.1 * c)), slot["max_minutes"])
        out.update(sets=1, target=max(5, minutes), rep_range=None, rpe=None, note="Easy pace where you could hold a conversation.")
        return out
    if deload:
        sets = (sets + 1) // 2
    step = 10 if slot["unit"] == "seconds" else 1
    target = slot["lo"] if deload else min(slot["lo"] + step * c, slot["hi"])
    rpe = slot["rpe"]
    if rpe is not None:
        rpe = max(5.0, rpe - 1.5) if deload else min(rpe + 0.5 * c, RPE_CAP[experience])
    out.update(sets=sets, target=target, rep_range=f"{slot['lo']}-{slot['hi']}", rpe=rpe)
    if slot["unit"] == "seconds":
        out["note"] = "Hold time in seconds, per side where it applies."
    return out


def _rules(ctx: dict, split_name: str, weeks: int) -> list[str]:
    sets_c, reps_c, sets_i, reps_i, rpe, _ = PRESCRIPTION[ctx["goal"]]
    rules = [
        f"Primary goal {ctx['goal']}: {sets_c} sets of {reps_c[0]}-{reps_c[1]} reps on main lifts and {sets_i} sets of {reps_i[0]}-{reps_i[1]} on accessories, starting near RPE {rpe}."
        + (" Beginners start 1 RPE lower and cap main-lift sets at 3." if ctx["experience"] == "beginner" else ""),
        f"Split chosen from {ctx['days']} days per week and the primary goal: {split_name}.",
        f"Each session is fitted to {ctx['minutes']} minutes: {WARMUP_MINUTES} minute warm-up when it has main lifts, about 0.75 minute per set plus rest "
        f"(main lifts {PRESCRIPTION[ctx['goal']][5]} min, accessories 1 min). Lowest-priority exercises are dropped first, then sets above 2, "
        f"and spare time adds sets to main lifts up to {SET_CAP[ctx['experience']]}.",
        f"Progression inside a 4-week block: each build week adds 1 rep to the target (up to the top of the range) and 0.5 RPE, "
        f"capped at RPE {RPE_CAP[ctx['experience']]} for {ctx['experience']} lifters.",
        "When you hit the top of the rep range at or below the target RPE on every set, add a small amount of load next time "
        "(about 2.5 kg for upper body, 5 kg for lower body) and go back to the bottom of the range.",
        "Every 4th week is a deload: about half the sets (rounded up), reps back at the bottom of the range, RPE 1.5 lower.",
        "Exercises come from a built-in library. Equipment you did not list is never used, and exercises tagged for a limitation you listed are removed.",
    ]
    if weeks < 4:
        rules.append("This plan is shorter than 4 weeks, so it has no deload week.")
    if ctx["goal"] in ("fat_loss", "general_health"):
        rules.append(f"Sessions end with a {FINISHER_MINUTES} minute easy cardio finisher when time allows.")
    if ctx["goal"] in ("endurance", "mobility"):
        rules.append("About half of the sessions are cardio or mobility blocks instead of lifting.")
    return rules


def generate_plan(profile: dict, weeks: int = 4, start: date | None = None) -> dict:
    gaps = missing_fields(profile)
    if gaps:
        raise PlanError(f"Profile is missing: {', '.join(gaps)}. Use profile_set first.")
    _num(weeks=(weeks, 1, 12, True))
    start = start or date.today()
    monday = start + timedelta(days=(-start.weekday()) % 7)
    ctx = {
        "goal": profile["goals"][0], "experience": profile["experience"], "days": profile["days_per_week"],
        "minutes": profile["session_minutes"], "equipment": set(profile["equipment"]),
        "excluded": set(profile.get("injuries", [])),
    }
    split_name, templates = choose_split(ctx["days"], ctx["goal"])
    finisher = ctx["goal"] in ("fat_loss", "general_health")
    seen: dict[str, int] = {}
    built: list[tuple[str, list[dict]]] = []
    warnings: list[str] = []
    for template in templates:
        variant = seen.get(template, 0)
        seen[template] = variant + 1
        slots, warn = _build_slots(template, variant, ctx, finisher and template not in ("cardio", "mobility"))
        warnings.extend(warn)
        warnings.extend(f"{template}: {n}" for n in _fit(slots, ctx["minutes"], ctx))
        built.append((template, slots))
    unknown = [t for t in profile.get("injuries", []) if t not in KNOWN_LIMITATIONS]
    if unknown:
        warnings.append(
            f"No library exercise is tagged for: {', '.join(unknown)}. Nothing was filtered for those, so check the plan yourself or ask a professional."
        )
    offsets = DAY_OFFSETS[ctx["days"]]
    plan_weeks = []
    for w in range(1, weeks + 1):
        c = (w - 1) % 4
        deload = c == 3
        sessions = []
        for i, (template, slots) in enumerate(built):
            day = monday + timedelta(weeks=w - 1, days=offsets[i])
            exercises = [_week_slot(s, c, deload, ctx["experience"]) for s in slots]
            sessions.append({
                "index": i, "name": template, "date": day.isoformat(), "weekday": WEEKDAYS[day.weekday()],
                "est_minutes": round(_estimate([_scaled(s, e) for s, e in zip(slots, exercises, strict=True)])),
                "exercises": exercises,
            })
        plan_weeks.append({"week": w, "phase": "deload" if deload else "build", "sessions": sessions})
    plan = {
        "notice": NOTICE, "start_date": monday.isoformat(), "weeks": weeks, "split": split_name,
        "profile": {k: profile[k] for k in (*REQUIRED_PROFILE_FIELDS, "injuries") if k in profile},
        "rules": _rules(ctx, split_name, weeks), "warnings": list(dict.fromkeys(warnings)), "schedule": plan_weeks, "adjustments": [],
    }
    plan["end_date"] = _last_date(plan)
    return plan


def _scaled(slot: dict, week_ex: dict) -> dict:
    """The base slot with this week's sets and minutes, for time estimates."""
    scaled = dict(slot)
    scaled["sets"] = week_ex["sets"]
    if slot["unit"] == "minutes":
        scaled["minutes"] = week_ex["target"]
    return scaled


def _last_date(plan: dict) -> str:
    return max(s["date"] for w in plan["schedule"] for s in w["sessions"])


def iter_sessions(plan: dict):
    for w in plan["schedule"]:
        for s in w["sessions"]:
            yield w, s


def session_on(plan: dict, day: date) -> tuple[dict, dict] | None:
    for w, s in iter_sessions(plan):
        if s["date"] == day.isoformat():
            return w, s
    return None


# ---------- adjusting ----------

def _ease(session: dict) -> None:
    for ex in session["exercises"]:
        if ex["unit"] == "minutes":
            ex["target"] = max(5, round(ex["target"] * 0.8))
        else:
            ex["sets"] = max(min(ex["sets"], 2), ex["sets"] - 1)
            if ex["rpe"] is not None:
                ex["rpe"] = max(5.0, ex["rpe"] - 1)


def _relabel(session: dict, day: date) -> None:
    session["date"] = day.isoformat()
    session["weekday"] = WEEKDAYS[day.weekday()]


def adjust_plan(plan: dict, reason: str, from_date: date, days_missed: int = 0, new_profile: dict | None = None) -> tuple[dict, list[str]]:
    """Return (revised plan, rules applied). The input plan is not modified."""
    new = copy.deepcopy(plan)
    rules: list[str] = []
    if reason == "low_readiness":
        end = from_date + timedelta(days=7)
        for _, s in iter_sessions(new):
            if from_date.isoformat() <= s["date"] < end.isoformat():
                _ease(s)
        rules.append("Low readiness: for sessions in the next 7 days, remove one set from each exercise (never below 2 sets) and lower RPE by 1 (never below 5). Cardio minutes drop by 20 percent.")
    elif reason == "missed_days":
        for _, s in iter_sessions(new):
            if s["date"] >= from_date.isoformat():
                _relabel(s, date.fromisoformat(s["date"]) + timedelta(days=days_missed))
        rules.append(f"Missed days: every session on or after {from_date.isoformat()} moves {days_missed} day(s) later, so the order and the deload week stay as planned.")
        if days_missed >= 7:
            first = from_date + timedelta(days=days_missed)
            for _, s in iter_sessions(new):
                if first.isoformat() <= s["date"] < (first + timedelta(days=7)).isoformat():
                    _ease(s)
            rules.append("After a gap of 7 days or more, the first week back is eased: one set fewer per exercise and RPE 1 lower.")
    else:
        assert new_profile is not None
        regenerated = generate_plan(new_profile, plan["weeks"], date.fromisoformat(plan["start_date"]))
        fresh = {(w["week"], s["index"]): s for w, s in iter_sessions(regenerated)}
        for w, s in iter_sessions(new):
            if s["date"] >= from_date.isoformat():
                repl = copy.deepcopy(fresh[(w["week"], s["index"])])
                repl["date"], repl["weekday"] = s["date"], s["weekday"]
                s.update(repl)
        new["profile"] = regenerated["profile"]
        new["warnings"] = regenerated["warnings"]
        new["rules"] = regenerated["rules"]
        what = "equipment list" if reason == "equipment_change" else "limitation list"
        rules.append(
            f"Sessions on or after {from_date.isoformat()} were rebuilt from the same rules with the new {what}. "
            "Earlier sessions are unchanged, and any earlier easing of sets or RPE on rebuilt sessions is replaced."
        )
    new["end_date"] = _last_date(new)
    new["adjustments"] = [*plan.get("adjustments", []), {"reason": reason, "from_date": from_date.isoformat()}]
    return new, rules


def _by_slot(exercises: list[dict]) -> dict[tuple[str, int], dict]:
    seen: Counter = Counter()
    out = {}
    for e in exercises:
        out[(e["slot"], seen[e["slot"]])] = e
        seen[e["slot"]] += 1
    return out


def diff_plans(old: dict, new: dict) -> list[dict]:
    changes: list[dict] = []
    new_sessions = {(w["week"], s["index"]): s for w, s in iter_sessions(new)}
    for w, s in iter_sessions(old):
        key = (w["week"], s["index"])
        t = new_sessions[key]
        base = {"week": w["week"], "session": s["name"]}
        if s["date"] != t["date"]:
            changes.append({**base, "field": "date", "from": s["date"], "to": t["date"]})
        old_by_slot, new_by_slot = _by_slot(s["exercises"]), _by_slot(t["exercises"])
        where = {**base, "date": t["date"]}
        for key in [*old_by_slot, *(k for k in new_by_slot if k not in old_by_slot)]:
            a, b = old_by_slot.get(key), new_by_slot.get(key)
            if a is None or b is None:
                changes.append({**where, "slot": key[0], "field": "exercise", "from": a and a["exercise"], "to": b and b["exercise"]})
                continue
            for field in ("exercise", "sets", "target", "rpe"):
                if a[field] != b[field]:
                    changes.append({**where, "slot": key[0], "exercise": b["exercise"], "field": field, "from": a[field], "to": b[field]})
    return changes


# ---------- review ----------

def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def review(plan: dict, rows: list[dict], as_of: date, weeks: int) -> dict:
    """Compare planned sessions in the window with logged sets. rows need date, exercise, rpe, weight_kg, reps."""
    first = as_of - timedelta(days=7 * weeks - 1)
    by_day: dict[str, list[dict]] = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    sessions, counts = [], {"done": 0, "partial": 0, "different_work": 0, "missed": 0, "not_loggable": 0}
    planned_total = logged_total = 0
    planned_rpes: list[float] = []
    logged_rpes: list[float] = []
    for w, s in iter_sessions(plan):
        if not (first.isoformat() <= s["date"] <= as_of.isoformat()):
            continue
        lifts = [e for e in s["exercises"] if e["unit"] == "reps"]
        if not lifts:
            counts["not_loggable"] += 1
            sessions.append({"date": s["date"], "week": w["week"], "session": s["name"], "status": "not_loggable"})
            continue
        day_rows = by_day.get(s["date"], [])
        wanted = {_norm(e["exercise"]): e for e in lifts}
        matched = [r for r in day_rows if _norm(r["exercise"]) in wanted]
        planned = sum(e["sets"] for e in lifts)
        logged = len(matched)
        status = "done" if logged >= planned else "partial" if logged else "different_work" if day_rows else "missed"
        counts[status] += 1
        planned_total += planned
        logged_total += min(logged, planned)
        planned_rpes += [e["rpe"] for e in lifts if e["rpe"] is not None for _ in range(e["sets"])]
        logged_rpes += [r["rpe"] for r in matched if r["rpe"]]
        sessions.append({
            "date": s["date"], "week": w["week"], "session": s["name"], "phase": w["phase"], "status": status,
            "planned_sets": planned, "logged_sets": logged,
        })
    due = len(sessions) - counts["not_loggable"]
    return {
        "window": {"from": first.isoformat(), "to": as_of.isoformat(), "weeks": weeks},
        "sessions": sessions,
        "totals": {
            **counts, "loggable_sessions_due": due,
            "set_completion_pct": round(100 * logged_total / planned_total, 1) if planned_total else None,
            "avg_planned_rpe": round(sum(planned_rpes) / len(planned_rpes), 1) if planned_rpes else None,
            "avg_logged_rpe": round(sum(logged_rpes) / len(logged_rpes), 1) if logged_rpes else None,
        },
    }


def overreaching_signal(rows: list[dict], as_of: date) -> dict:
    """Weekly logged volume and RPE across all exercises, judged with the same thresholds as training_check_overreaching."""
    volume: dict[str, float] = {}
    rpes: dict[str, list[float]] = {}
    for r in rows:
        d = date.fromisoformat(r["date"])
        wk = (d - timedelta(days=d.weekday())).isoformat()
        volume[wk] = volume.get(wk, 0) + (r["weight_kg"] or 0) * (r["reps"] or 0)
        if r["rpe"]:
            rpes.setdefault(wk, []).append(r["rpe"])
    current = (as_of - timedelta(days=as_of.weekday())).isoformat()
    weeks = sorted(w for w in volume if w != current or as_of.weekday() == 6)
    if len(weeks) < 2:
        return {"risk": "insufficient_data", "note": "Needs two full logged weeks. The current week is not counted until it ends."}
    vols = [volume[w] for w in weeks]
    avg = [sum(rpes[w]) / len(rpes[w]) for w in weeks if w in rpes]
    vol_up = vols[-1] > vols[0] * VOLUME_RISE
    rpe_up = len(avg) >= 2 and avg[-1] - avg[0] >= RPE_RISE
    risk = "elevated" if vol_up and rpe_up else "moderate" if vol_up else "low"
    return {"risk": risk, "weeks_analyzed": len(weeks), "weekly_volume_kg": {w: round(volume[w], 1) for w in weeks}}

