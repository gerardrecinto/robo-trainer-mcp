"""Profile, exercise search and plan tools, run through the real server against a real SQLite file."""
from datetime import date, timedelta

import pytest

from robo_trainer.exercises import BY_NAME, LIBRARY
from tests.helpers import call, purge_robo_trainer

MONDAY = "2026-11-09"
PROFILE = dict(
    goals=["hypertrophy"], experience="intermediate", equipment=["dumbbells", "bench", "pull_up_bar", "barbell"],
    days_per_week=4, session_minutes=60, injuries=[],
)


@pytest.fixture
def make_server(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path))

    def build():
        purge_robo_trainer()
        from robo_trainer.server import create_server

        return create_server()

    return build


@pytest.fixture
def server(make_server):
    return make_server()


@pytest.fixture
def planned(server):
    call(server, "profile_set", **PROFILE)
    return call(server, "plan_generate", weeks=4, start_date=MONDAY)


def sessions(plan):
    return [s for w in plan["schedule"] for s in w["sessions"]]


def exercise_names(plan):
    return {e["exercise"] for s in sessions(plan) for e in s["exercises"]}


# ---------- profile ----------

def test_profile_get_lists_every_missing_field_when_empty(server):
    out = call(server, "profile_get")
    assert out["complete"] is False
    assert out["missing_fields"] == ["goals", "experience", "equipment", "days_per_week", "session_minutes"]


def test_profile_set_merges_fields_and_survives_restart(make_server):
    server = make_server()
    call(server, "profile_set", goals=["strength", "mobility"], experience="Beginner")
    saved = call(server, "profile_set", days_per_week=3, injuries=["Knees", "low back"])
    assert saved["profile"]["goals"] == ["strength", "mobility"]
    assert saved["profile"]["experience"] == "beginner"
    assert saved["profile"]["injuries"] == ["knee", "lower_back"]
    assert saved["missing_fields"] == ["equipment", "session_minutes"]
    restarted = make_server()
    assert call(restarted, "profile_get")["profile"]["days_per_week"] == 3


@pytest.mark.parametrize("bad, fragment", [
    ({"goals": ["bulking"]}, "Unknown goal"),
    ({"goals": []}, "non-empty"),
    ({"goals": ["strength", "hypertrophy", "fat_loss", "endurance"]}, "at most 3"),
    ({"experience": "expert"}, "experience must be one of"),
    ({"equipment": ["treadmill"]}, "Unknown equipment"),
    ({"days_per_week": 0}, "between 1 and 7"),
    ({"days_per_week": 8}, "between 1 and 7"),
    ({"session_minutes": 10}, "between 15 and 180"),
    ({"injuries": ["x" * 41]}, "40 characters"),
    ({}, "Nothing to save"),
])
def test_profile_set_rejects_bad_input_with_a_clear_message(server, bad, fragment):
    out = call(server, "profile_set", **bad)
    assert fragment in out["error"]
    assert call(server, "profile_get")["profile"] == {}


def test_planner_rejects_fractional_days_and_non_list_injuries():
    from robo_trainer.planner import PlanError, clean_profile_update

    with pytest.raises(PlanError, match="whole number"):
        clean_profile_update(days_per_week=2.5)
    with pytest.raises(PlanError, match="list"):
        clean_profile_update(injuries="knee")


# ---------- exercise search ----------

def test_library_alternatives_all_exist_and_every_pattern_has_a_bodyweight_or_band_option():
    for ex in LIBRARY:
        assert ex.alternatives, ex.name
        assert all(a in BY_NAME for a in ex.alternatives), ex.name


def test_search_filters_by_muscle(server):
    out = call(server, "exercise_search", muscle="chest")
    assert out["count"] > 0
    assert all("chest" in e["muscles"] for e in out["exercises"])


def test_search_filters_by_equipment(server):
    out = call(server, "exercise_search", equipment=["dumbbells"], limit=100)
    allowed = {"dumbbells", "bodyweight"}
    assert out["count"] > 0
    assert all(set(e["equipment"]) <= allowed for e in out["exercises"])
    assert not any("Barbell Bench Press" == e["name"] for e in out["exercises"])


def test_search_excludes_only_exercises_tagged_for_the_limitation(server):
    everything = call(server, "exercise_search", limit=100)["exercises"]
    filtered = call(server, "exercise_search", exclude_limitations=["Knees"], limit=100)["exercises"]
    assert filtered and all("knee" not in e["limitation_tags"] for e in filtered)
    expected = {e["name"] for e in everything if "knee" not in e["limitation_tags"]}
    assert {e["name"] for e in filtered} == expected


def test_search_rejects_unknown_muscle_and_difficulty(server):
    assert "Unknown muscle group" in call(server, "exercise_search", muscle="wings")["error"]
    assert "max_difficulty" in call(server, "exercise_search", max_difficulty="elite")["error"]
    assert "limit" in call(server, "exercise_search", limit=0)["error"]


# ---------- plan_generate ----------

def test_plan_generate_needs_a_complete_profile(server):
    call(server, "profile_set", goals=["strength"])
    out = call(server, "plan_generate")
    assert "missing: experience, equipment, days_per_week, session_minutes" in out["error"]


def test_plan_generate_validates_weeks_and_date(server):
    call(server, "profile_set", **PROFILE)
    assert "weeks" in call(server, "plan_generate", weeks=0)["error"]
    assert "weeks" in call(server, "plan_generate", weeks=13)["error"]
    assert "YYYY-MM-DD" in call(server, "plan_generate", start_date="11/09/2026")["error"]
    assert "calendar" in call(server, "plan_generate", start_date="2026-02-30")["error"]


def test_plan_is_deterministic_across_calls_and_fresh_data_folders(make_server, tmp_path, monkeypatch):
    first_server = make_server()
    call(first_server, "profile_set", **PROFILE)
    first = call(first_server, "plan_generate", start_date=MONDAY)
    again = call(first_server, "plan_generate", start_date=MONDAY)
    assert again.pop("replaced_existing_plan") is True
    assert first.pop("replaced_existing_plan") is False
    assert first == again
    other = tmp_path / "other"
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(other))
    second_server = make_server()
    call(second_server, "profile_set", **PROFILE)
    third = call(second_server, "plan_generate", start_date=MONDAY)
    third.pop("replaced_existing_plan")
    assert third == first


def test_plan_starts_on_a_monday_and_includes_rules_and_notice(planned):
    assert planned["start_date"] == MONDAY
    assert len(planned["rules"]) >= 6
    assert any("deload" in r.lower() for r in planned["rules"])
    assert "not medical advice" in planned["notice"]
    assert date.fromisoformat(sessions(planned)[0]["date"]).weekday() == 0


def test_start_date_midweek_rolls_to_next_monday(server):
    call(server, "profile_set", **PROFILE)
    plan = call(server, "plan_generate", start_date="2026-11-11")
    assert plan["start_date"] == "2026-11-16"


@pytest.mark.parametrize("days, goal, expected", [
    (1, "strength", ["full_a"]),
    (3, "strength", ["full_a", "full_b", "full_c"]),
    (4, "hypertrophy", ["upper", "lower", "upper", "lower"]),
    (5, "hypertrophy", ["push", "pull", "legs", "upper", "lower"]),
    (6, "fat_loss", ["push", "pull", "legs", "push", "pull", "legs"]),
    (7, "general_health", ["push", "pull", "legs", "push", "pull", "legs", "mobility"]),
    (4, "endurance", ["full_a", "cardio", "full_b", "cardio"]),
    (1, "endurance", ["cardio"]),
    (3, "mobility", ["full_a", "mobility", "full_b"]),
])
def test_split_follows_days_and_primary_goal(server, days, goal, expected):
    call(server, "profile_set", **{**PROFILE, "goals": [goal], "days_per_week": days})
    plan = call(server, "plan_generate", weeks=1, start_date=MONDAY)
    assert [s["name"] for s in plan["schedule"][0]["sessions"]] == expected


@pytest.mark.parametrize("goal", ["strength", "hypertrophy", "fat_loss", "endurance", "mobility", "general_health"])
@pytest.mark.parametrize("minutes", [20, 30, 45, 90])
def test_sessions_fit_the_time_budget(server, goal, minutes):
    call(server, "profile_set", **{**PROFILE, "goals": [goal], "session_minutes": minutes, "days_per_week": 5})
    plan = call(server, "plan_generate", start_date=MONDAY)
    assert plan["schedule"][0]["sessions"]
    for s in sessions(plan):
        assert s["est_minutes"] <= minutes + 1 or any("could not fit" in w for w in plan["warnings"]), (s["name"], s["est_minutes"])


def test_plan_only_uses_owned_equipment(server):
    call(server, "profile_set", **{**PROFILE, "equipment": ["resistance_bands"]})
    plan = call(server, "plan_generate", start_date=MONDAY)
    names = exercise_names(plan)
    assert names
    for name in names:
        assert set(BY_NAME[name].equipment) <= {"bodyweight", "resistance_bands"}, name
    for s in sessions(plan):
        for e in s["exercises"]:
            for alt in e["alternatives"]:
                assert set(BY_NAME[alt].equipment) <= {"bodyweight", "resistance_bands"}


def test_plan_skips_exercises_tagged_for_a_listed_limitation(server):
    call(server, "profile_set", **{**PROFILE, "injuries": ["shoulder", "knee"]})
    plan = call(server, "plan_generate", start_date=MONDAY)
    for name in exercise_names(plan):
        assert not ({"shoulder", "knee"} & set(BY_NAME[name].limitations)), name
    assert "Back Squat" not in exercise_names(plan)


def test_unrecognised_limitation_tag_is_called_out_not_silently_ignored(server):
    call(server, "profile_set", **{**PROFILE, "injuries": ["migraine"]})
    plan = call(server, "plan_generate", start_date=MONDAY)
    assert any("migraine" in w and "Nothing was filtered" in w for w in plan["warnings"])


def test_slot_with_no_valid_exercise_is_reported(server):
    call(server, "profile_set", **{**PROFILE, "equipment": ["dumbbells"], "injuries": ["knee"], "days_per_week": 4})
    plan = call(server, "plan_generate", start_date=MONDAY)
    assert any("no squat exercise fits" in w for w in plan["warnings"])


def test_deload_week_cuts_sets_and_effort_and_progression_builds_before_it(planned):
    weeks = planned["schedule"]
    assert [w["phase"] for w in weeks] == ["build", "build", "build", "deload"]
    for build_session, deload_session in zip(weeks[0]["sessions"], weeks[3]["sessions"], strict=True):
        for b, d in zip(build_session["exercises"], deload_session["exercises"], strict=True):
            assert d["exercise"] == b["exercise"]
            assert d["sets"] == (b["sets"] + 1) // 2
            if b["rpe"] is not None:
                assert d["rpe"] < b["rpe"]
    first, second, third = (w["sessions"][0]["exercises"][0] for w in weeks[:3])
    assert (second["target"], third["target"]) == (first["target"] + 1, first["target"] + 2)
    assert first["rpe"] < second["rpe"] < third["rpe"]
    assert weeks[3]["sessions"][0]["exercises"][0]["target"] == first["target"]


def test_plans_shorter_than_four_weeks_have_no_deload_and_eight_weeks_have_two(server):
    call(server, "profile_set", **PROFILE)
    three = call(server, "plan_generate", weeks=3, start_date=MONDAY)
    assert all(w["phase"] == "build" for w in three["schedule"])
    assert any("no deload" in r for r in three["rules"])
    eight = call(server, "plan_generate", weeks=8, start_date=MONDAY)
    assert [w["phase"] for w in eight["schedule"]].count("deload") == 2
    assert eight["schedule"][7]["phase"] == "deload"


def test_rpe_never_passes_the_cap_for_the_experience_level(server):
    call(server, "profile_set", **{**PROFILE, "experience": "beginner", "goals": ["strength"]})
    plan = call(server, "plan_generate", weeks=12, start_date=MONDAY)
    rpes = [e["rpe"] for s in sessions(plan) for e in s["exercises"] if e["rpe"] is not None]
    assert max(rpes) <= 8.0 and min(rpes) >= 5.0


def test_beginner_main_lifts_stay_at_three_sets_or_fewer(server):
    call(server, "profile_set", **{**PROFILE, "experience": "beginner", "goals": ["strength"], "session_minutes": 120})
    plan = call(server, "plan_generate", start_date=MONDAY)
    assert max(e["sets"] for s in sessions(plan) for e in s["exercises"]) <= 3


def test_fat_loss_sessions_end_with_a_cardio_finisher_when_time_allows(server):
    call(server, "profile_set", **{**PROFILE, "goals": ["fat_loss"], "session_minutes": 75, "equipment": ["dumbbells", "bench"]})
    plan = call(server, "plan_generate", start_date=MONDAY)
    last = plan["schedule"][0]["sessions"][0]["exercises"][-1]
    assert last["unit"] == "minutes" and last["target"] == 10


# ---------- plan_get_today ----------

def test_get_today_before_any_plan(server):
    assert call(server, "plan_get_today", date=MONDAY)["status"] == "no_plan"


def test_get_today_returns_session_rest_day_and_outside_plan(planned, server):
    training = call(server, "plan_get_today", date=MONDAY)
    assert training["status"] == "training_day"
    assert training["session"]["name"] == "upper" and training["week"] == 1
    rest = call(server, "plan_get_today", date="2026-11-11")
    assert rest["status"] == "rest_day" and rest["next_session_date"] == "2026-11-12"
    assert call(server, "plan_get_today", date="2027-03-01")["status"] == "outside_plan"
    assert "YYYY-MM-DD" in call(server, "plan_get_today", date="today")["error"]


def test_get_today_defaults_to_the_current_date(planned, server):
    out = call(server, "plan_get_today")
    assert out["date"] == date.today().isoformat()


# ---------- plan_adjust ----------

def test_adjust_needs_a_plan_and_a_known_reason(server):
    assert "No plan stored" in call(server, "plan_adjust", reason="low_readiness")["error"]
    call(server, "profile_set", **PROFILE)
    call(server, "plan_generate", start_date=MONDAY)
    assert "reason must be one of" in call(server, "plan_adjust", reason="bored")["error"]


def test_low_readiness_eases_only_the_next_seven_days_and_reports_a_diff(planned, server):
    out = call(server, "plan_adjust", reason="low_readiness", from_date=MONDAY)
    assert out["changes"] and set(out["summary"]) == {"sets", "rpe"}
    before = {(s["date"], i): e for s in sessions(planned) for i, e in enumerate(s["exercises"])}
    for s in sessions(out["revised_plan"]):
        for i, e in enumerate(s["exercises"]):
            old = before[(s["date"], i)]
            if s["date"] < (date.fromisoformat(MONDAY) + timedelta(days=7)).isoformat():
                assert e["sets"] <= old["sets"] and e["rpe"] == (None if old["rpe"] is None else max(5.0, old["rpe"] - 1))
                assert e["sets"] >= min(old["sets"], 2)
            else:
                assert e == old
    assert all(c["week"] == 1 for c in out["changes"])
    assert out["rules_applied"]


def test_adjusted_plan_is_stored_and_old_plan_is_untouched_in_the_diff(planned, server):
    out = call(server, "plan_adjust", reason="low_readiness", from_date=MONDAY)
    stored = call(server, "plan_get_today", date=MONDAY)["session"]
    assert stored == out["revised_plan"]["schedule"][0]["sessions"][0]
    assert out["revised_plan"]["adjustments"] == [{"reason": "low_readiness", "from_date": MONDAY}]


def test_missed_days_shift_later_sessions_and_keep_the_deload_last(planned, server):
    out = call(server, "plan_adjust", reason="missed_days", from_date="2026-11-12", days_missed=2)
    assert {c["field"] for c in out["changes"]} == {"date"}
    revised = sessions(out["revised_plan"])
    original = sessions(planned)
    for old, new in zip(original, revised, strict=True):
        shift = 2 if old["date"] >= "2026-11-12" else 0
        assert new["date"] == (date.fromisoformat(old["date"]) + timedelta(days=shift)).isoformat()
    assert out["revised_plan"]["schedule"][3]["phase"] == "deload"
    assert out["revised_plan"]["end_date"] == (date.fromisoformat(planned["end_date"]) + timedelta(days=2)).isoformat()


def test_a_week_or_more_missed_eases_the_first_week_back(planned, server):
    out = call(server, "plan_adjust", reason="missed_days", from_date="2026-11-16", days_missed=7)
    assert {"date", "sets", "rpe"} <= set(out["summary"])
    back = [s for s in sessions(out["revised_plan"]) if "2026-11-23" <= s["date"] < "2026-11-30"]
    original = {(w["week"], s["index"]): s for w in planned["schedule"] for s in w["sessions"]}
    easier = False
    for s in back:
        for w in out["revised_plan"]["schedule"]:
            if s in w["sessions"]:
                old = original[(w["week"], s["index"])]
                easier |= s["exercises"][0]["rpe"] < old["exercises"][0]["rpe"]
    assert easier


def test_missed_days_needs_a_sensible_count(planned, server):
    assert "days_missed" in call(server, "plan_adjust", reason="missed_days")["error"]
    assert "days_missed" in call(server, "plan_adjust", reason="missed_days", days_missed=40)["error"]


def test_equipment_change_swaps_exercises_from_the_date_on_and_updates_the_profile(planned, server):
    out = call(server, "plan_adjust", reason="equipment_change", equipment=["resistance_bands"], from_date="2026-11-16")
    swaps = [c for c in out["changes"] if c["field"] == "exercise"]
    assert swaps and all(c["date"] >= "2026-11-16" for c in out["changes"])
    revised = sessions(out["revised_plan"])
    assert [s for s in revised if s["date"] < "2026-11-16"] == [s for s in sessions(planned) if s["date"] < "2026-11-16"]
    for s in revised:
        if s["date"] >= "2026-11-16":
            assert all(set(BY_NAME[e["exercise"]].equipment) <= {"bodyweight", "resistance_bands"} for e in s["exercises"])
    assert call(server, "profile_get")["profile"]["equipment"] == ["resistance_bands"]


def test_equipment_change_validates_input(planned, server):
    assert "new equipment list" in call(server, "plan_adjust", reason="equipment_change")["error"]
    assert "Unknown equipment" in call(server, "plan_adjust", reason="equipment_change", equipment=["sled"])["error"]


def test_injury_removes_tagged_exercises_going_forward_and_is_remembered(planned, server):
    assert any("elbow" in BY_NAME[n].limitations for n in exercise_names(planned))
    out = call(server, "plan_adjust", reason="injury", limitation="Elbow", from_date=MONDAY)
    for name in exercise_names(out["revised_plan"]):
        assert "elbow" not in BY_NAME[name].limitations
    assert {c["field"] for c in out["changes"]} >= {"exercise"}
    assert call(server, "profile_get")["profile"]["injuries"] == ["elbow"]
    again = call(server, "plan_adjust", reason="injury", limitation="wrist, ankle", from_date=MONDAY)
    assert call(server, "profile_get")["profile"]["injuries"] == ["elbow", "wrist", "ankle"]
    assert again["revised_plan"]["profile"]["injuries"] == ["elbow", "wrist", "ankle"]


def test_injury_needs_a_tag(planned, server):
    assert "limitation tag" in call(server, "plan_adjust", reason="injury")["error"]


# ---------- plan_review_progress ----------

def log_session(server, session, sets_each=None, **kw):
    for e in session["exercises"]:
        if e["unit"] != "reps":
            continue
        for _ in range(sets_each if sets_each is not None else e["sets"]):
            call(server, "training_log_set", exercise=e["exercise"].lower().replace(" ", "_"), weight_kg=50, reps=8,
                 rpe=e["rpe"] or 0, date=session["date"], **kw)


def test_review_needs_a_plan_and_valid_input(server):
    assert "No plan stored" in call(server, "plan_review_progress")["error"]
    call(server, "profile_set", **PROFILE)
    call(server, "plan_generate", start_date=MONDAY)
    assert "weeks" in call(server, "plan_review_progress", weeks=0)["error"]
    assert "YYYY-MM-DD" in call(server, "plan_review_progress", as_of="soon")["error"]


def test_review_compares_planned_and_logged_sets(planned, server):
    s = sessions(planned)
    log_session(server, s[0])                      # done
    log_session(server, s[1], sets_each=1)         # partial
    call(server, "training_log_set", exercise="running", weight_kg=1, reps=1, date=s[3]["date"])  # other work only
    out = call(server, "plan_review_progress", weeks=1, as_of="2026-11-15")
    statuses = [x["status"] for x in out["sessions"]]
    assert statuses == ["done", "partial", "missed", "different_work"]
    totals = out["totals"]
    assert (totals["done"], totals["partial"], totals["missed"], totals["different_work"]) == (1, 1, 1, 1)
    assert totals["loggable_sessions_due"] == 4
    planned_sets = sum(x["planned_sets"] for x in out["sessions"])
    logged = sum(min(x["logged_sets"], x["planned_sets"]) for x in out["sessions"])
    assert totals["set_completion_pct"] == round(100 * logged / planned_sets, 1)
    assert out["sessions"][0]["logged_sets"] == out["sessions"][0]["planned_sets"]
    assert totals["avg_planned_rpe"] is not None and totals["avg_logged_rpe"] is not None


def test_review_ignores_future_sessions_and_uses_the_window(planned, server):
    out = call(server, "plan_review_progress", weeks=1, as_of="2026-11-10")
    assert [x["date"] for x in out["sessions"]] == [MONDAY, "2026-11-10"]
    wide = call(server, "plan_review_progress", weeks=4, as_of="2026-11-10")
    assert wide["window"]["from"] == "2026-10-14"


def test_review_reports_recovery_context_from_existing_logs(planned, server):
    call(server, "recovery_log_sleep", hours=6, quality=5, date="2026-11-10")
    call(server, "recovery_log_sleep", hours=8, quality=7, date="2026-11-11")
    call(server, "mental_log_mood", mood=6, energy=6, stress=4, date="2026-11-10")
    ctx = call(server, "plan_review_progress", weeks=1, as_of="2026-11-15")["recovery_context"]
    assert ctx["avg_sleep_hours"] == 7.0 and ctx["avg_sleep_quality"] == 6.0
    assert ctx["avg_stress"] == 4.0 and ctx["sleep_days_logged"] == 2


def test_review_flags_overreaching_with_the_existing_thresholds(planned, server):
    for week, (weight, rpe) in enumerate([(50, 7.0), (60, 8.0)]):
        d = (date(2026, 11, 2) + timedelta(weeks=week)).isoformat()
        for _ in range(3):
            call(server, "training_log_set", exercise="squat", weight_kg=weight, reps=5, rpe=rpe, date=d)
    out = call(server, "plan_review_progress", weeks=3, as_of="2026-11-22")
    assert out["overreaching"]["risk"] == "elevated"
    assert call(server, "plan_review_progress", weeks=1, as_of="2026-11-22")["overreaching"]["risk"] == "insufficient_data"


def test_cardio_and_mobility_sessions_are_not_loggable_and_not_counted(server):
    call(server, "profile_set", **{**PROFILE, "goals": ["endurance"], "days_per_week": 4})
    call(server, "plan_generate", start_date=MONDAY)
    out = call(server, "plan_review_progress", weeks=1, as_of="2026-11-15")
    assert out["totals"]["not_loggable"] == 2
    assert out["totals"]["loggable_sessions_due"] == 2
    assert any("not loggable" in n for n in out["notes"])


def test_existing_training_log_data_is_not_changed_by_planning(planned, server):
    call(server, "training_log_set", exercise="squat", weight_kg=100, reps=5, date="2026-11-09")
    call(server, "plan_review_progress", weeks=1, as_of="2026-11-15")
    call(server, "plan_adjust", reason="low_readiness", from_date=MONDAY)
    history = call(server, "training_get_session_history", exercise="squat")
    assert history[0]["sets"][0]["weight_kg"] == 100


def test_injury_diff_reports_the_removed_slot_without_shifting_the_rest(server):
    call(server, "profile_set", **{**PROFILE, "equipment": ["dumbbells", "bench", "pull_up_bar"], "days_per_week": 3, "session_minutes": 45})
    call(server, "plan_generate", start_date=MONDAY)
    out = call(server, "plan_adjust", reason="injury", limitation="shoulder", from_date=MONDAY)
    removed = [c for c in out["changes"] if c["to"] is None]
    assert any(c["from"] == "Dumbbell Bench Press" and c["slot"] == "horizontal_push" for c in removed)
    untouched = [c for c in out["changes"] if c["week"] == 1 and c["session"] == "full_a" and c.get("exercise") == "Inverted Row"]
    assert untouched == []


def test_readme_plan_example_matches_real_output(server):
    from tests.helpers import REPO_ROOT

    readme = (REPO_ROOT / "README.md").read_text()
    call(server, "profile_set", goals=["hypertrophy"], experience="intermediate", equipment=["dumbbells", "bench", "pull_up_bar"],
         days_per_week=3, session_minutes=45)
    plan = call(server, "plan_generate", weeks=4, start_date="2026-11-09")
    for week_index in (0, 3):
        week = plan["schedule"][week_index]
        first = week["sessions"][0]
        assert f"Week {week['week']} ({week['phase']}), {first['weekday']} {first['date']}, {first['name']}, about {first['est_minutes']} min" in readme
        for e in first["exercises"]:
            if e["unit"] == "seconds":
                line = f"{e['exercise']}: {e['sets']} x {e['target']} s hold (range {e['rep_range']})"
            else:
                line = f"{e['exercise']}: {e['sets']} x {e['target']} reps (range {e['rep_range']}), RPE {e['rpe']}"
            assert line in readme, line
    assert "about 44 min each" in readme and all(s["est_minutes"] == 44 for s in plan["schedule"][0]["sessions"])
    assert [s["weekday"] for s in plan["schedule"][0]["sessions"]] == ["Mon", "Wed", "Fri"]
