"""Run the real server against a real SQLite file. No stubs."""
import pytest

from tests.helpers import EXPECTED_TOOLS, call, purge_robo_trainer, tool_names


@pytest.fixture
def make_server(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path))

    def build():
        purge_robo_trainer()
        from robo_trainer.server import create_server

        return create_server()

    return build


def test_registers_every_expected_tool(make_server):
    names = tool_names(make_server())
    assert names == EXPECTED_TOOLS, {
        "missing": sorted(EXPECTED_TOOLS - names),
        "unexpected": sorted(names - EXPECTED_TOOLS),
    }


def test_every_tool_has_a_description(make_server):
    import asyncio

    server = make_server()
    missing = [t.name for t in asyncio.run(server.list_tools()) if not (t.description or "").strip()]
    assert not missing


def test_training_round_trip_is_stored_and_survives_a_restart(make_server):
    server = make_server()
    logged = call(server, "training_log_set", exercise="squat", weight_kg=100, reps=5, rpe=8, date="2026-01-05")
    assert logged["logged"]["set"] == 1
    call(server, "training_log_set", exercise="squat", weight_kg=110, reps=3, date="2026-01-05")

    restarted = make_server()
    prs = call(restarted, "training_get_prs")
    squat = next(p for p in prs if p["exercise"] == "squat")
    assert squat["weight_kg"] == 110
    history = call(restarted, "training_get_session_history", exercise="squat")
    assert len(history[0]["sets"]) == 2


def test_nutrition_summary_adds_up(make_server):
    server = make_server()
    call(server, "nutrition_set_goals", calories=2400, protein_g=170, carbs_g=250, fat_g=70)
    call(server, "nutrition_log_meal", food_name="rice", grams=200, calories=260, protein_g=5, carbs_g=56, fat_g=1, date="2026-01-05")
    call(server, "nutrition_log_meal", food_name="chicken", grams=150, calories=250, protein_g=46, carbs_g=0, fat_g=5, date="2026-01-05")
    summary = call(server, "nutrition_get_daily_summary", date="2026-01-05")
    assert summary["actual"]["calories"] == 510
    assert summary["actual"]["protein_g"] == 51
    assert summary["remaining"]["calories"] == 1890


def test_bodyweight_sleep_mood_and_strongman_are_stored(make_server):
    from datetime import date

    today = date.today().isoformat()
    server = make_server()
    call(server, "training_log_bodyweight", weight_kg=90.5, date=today)
    assert call(server, "training_get_bodyweight_trend", days=7)["latest_kg"] == 90.5
    call(server, "recovery_log_sleep", hours=7.5, quality=8, hrv_ms=62, date=today)
    assert call(server, "recovery_get_sleep_trend", days=7)["averages"]["hours"] == 7.5
    call(server, "mental_log_mood", mood=7, energy=6, stress=3, date=today)
    assert call(server, "mental_get_mood_trend", days=7)["averages"]["mood"] == 7.0
    call(server, "strongman_log_event", event_name="Log Press", implement_weight_kg=100, reps=3, date=today)
    prs = call(server, "strongman_get_event_prs")
    assert any(p["event_name"] == "log_press" and p["weight_kg"] == 100 for p in prs)


def test_calculators_match_hand_computed_values(make_server):
    server = make_server()
    one_rm = call(server, "training_calculate_1rm", weight_kg=100, reps=5)
    assert one_rm["estimated_1rm_kg"] == 116.7
    assert call(server, "pl_analyze_sbd_ratio", squat_kg=200, bench_kg=130, deadlift_kg=250)["total_kg"] == 580
