"""Bad dates, windows and strongman values return a clear error and never reach the database."""
import os
import stat

import pytest

from tests.helpers import call, purge_robo_trainer


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path))
    purge_robo_trainer()
    from robo_trainer.server import create_server

    return create_server()


@pytest.mark.parametrize("tool,args", [
    ("training_log_set", {"exercise": "squat", "weight_kg": 100, "reps": 5}),
    ("training_log_bodyweight", {"weight_kg": 80}),
    ("nutrition_log_meal", {"food_name": "egg", "grams": 50, "calories": 70, "protein_g": 6, "carbs_g": 1, "fat_g": 5}),
    ("recovery_log_sleep", {"hours": 7, "quality": 7}),
    ("mental_log_mood", {"mood": 5, "energy": 5, "stress": 5}),
    ("strongman_log_event", {"event_name": "yoke", "implement_weight_kg": 200}),
])
@pytest.mark.parametrize("bad", ["garbage", "2026-13-40", "2026-1-5", "2026-02-30"])
def test_log_tools_reject_a_bad_date(server, tool, args, bad):
    assert "date" in call(server, tool, date=bad, **args)["error"]


def test_a_rejected_date_leaves_the_trend_tools_working(server):
    call(server, "training_log_set", exercise="squat", weight_kg=100, reps=5, date="garbage")
    assert "sample_data" in call(server, "training_get_volume_trend", exercise="squat")
    assert "sample_data" in call(server, "training_check_overreaching", exercise="squat")


def test_daily_summary_rejects_a_bad_date(server):
    assert "date" in call(server, "nutrition_get_daily_summary", date="yesterday")["error"]


@pytest.mark.parametrize("tool,args", [
    ("training_get_bodyweight_trend", {"days": -5}),
    ("training_get_bodyweight_trend", {"days": 99999999999}),
    ("recovery_get_sleep_trend", {"days": 0}),
    ("mental_get_mood_trend", {"days": -3}),
    ("training_get_volume_trend", {"exercise": "squat", "weeks": -2}),
    ("training_check_overreaching", {"exercise": "squat", "weeks": 0}),
    ("training_get_session_history", {"exercise": "squat", "limit": -1}),
    ("nutrition_search_food", {"query": "egg", "limit": 0}),
])
def test_window_and_limit_arguments_are_range_checked(server, tool, args):
    assert "must be between" in call(server, tool, **args)["error"]


@pytest.mark.parametrize("args", [
    {"event_name": "", "implement_weight_kg": 100},
    {"event_name": "yoke", "implement_weight_kg": -50},
    {"event_name": "yoke", "implement_weight_kg": 1e308},
    {"event_name": "yoke", "reps": -3},
    {"event_name": "yoke", "time_seconds": -1},
    {"event_name": "yoke", "distance_meters": -1},
])
def test_strongman_log_rejects_bad_values(server, args):
    assert "error" in call(server, "strongman_log_event", **args)
    assert "sample_data" in call(server, "strongman_get_event_prs")


def test_strongman_standards_and_sbd_ratio_reject_negatives(server):
    assert "error" in call(server, "strongman_competition_standards", event_name="yoke", implement_weight_kg=-5)
    assert "error" in call(server, "pl_analyze_sbd_ratio", squat_kg=-100, bench_kg=50, deadlift_kg=300)


def test_good_values_still_work(server):
    assert call(server, "training_log_set", exercise="squat", weight_kg=100, reps=5, date="2026-01-05")["logged"]
    assert call(server, "strongman_log_event", event_name="Yoke", implement_weight_kg=200, time_seconds=12.5)["logged"]
    assert call(server, "pl_analyze_sbd_ratio", squat_kg=200, bench_kg=130, deadlift_kg=240)["weakest_lift"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_data_folder_database_and_audit_log_are_owner_only(server, tmp_path):
    call(server, "training_log_bodyweight", weight_kg=80)
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "data.db").stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "audit.log").stat().st_mode) == 0o600
