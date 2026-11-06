"""Correctness checks for the fitness calculations, against values worked out by hand or by an independent source."""
from datetime import date, timedelta

import pytest

from robo_trainer.validation import check
from tests.helpers import call, purge_robo_trainer


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path))
    purge_robo_trainer()
    from robo_trainer.server import create_server

    return create_server()


def test_dots_women_matches_a_published_worked_example(server):
    # 60 kg woman, 320 kg total scores 354.73 (two independent sources agree on the coefficients).
    assert call(server, "pl_calculate_dots", bodyweight_kg=60, total_kg=320, sex="f")["dots_score"] == pytest.approx(354.73, abs=0.05)


def test_dots_men_and_wilks_regression_values(server):
    # Regression values for the men's DOTS and the 1994 Wilks formulas. Only the women's DOTS example above is independently sourced.
    assert call(server, "pl_calculate_dots", bodyweight_kg=90, total_kg=600, sex="m")["dots_score"] == pytest.approx(387.96, abs=0.05)
    result = call(server, "pl_calculate_wilks", bodyweight_kg=90, total_kg=600, sex="m")
    assert result["wilks_score"] == pytest.approx(383.04, abs=0.05)
    assert result["formula"] == "Wilks (1994)"


def test_unknown_sex_is_rejected_instead_of_scored_as_female(server):
    assert "error" in call(server, "pl_calculate_dots", bodyweight_kg=80, total_kg=500, sex="x")


def test_one_rep_max_formulas_and_high_rep_warning(server):
    five = call(server, "training_calculate_1rm", weight_kg=100, reps=5)
    assert five["estimated_1rm_kg"] == 116.7   # Epley: 100 * (1 + 5/30)
    assert five["brzycki_1rm_kg"] == 112.5     # Brzycki: 100 * 36 / 32
    assert "note" not in five
    assert "note" in call(server, "training_calculate_1rm", weight_kg=60, reps=15)


def test_rpe_estimate_uses_reps_in_reserve(server):
    # 5 reps at RPE 10 is 86.3 percent of 1RM; 5 reps at RPE 9 is like 6 to failure, 83.7 percent.
    assert call(server, "training_estimate_1rm_from_rpe", weight_kg=100, reps=5, rpe=10)["percent_of_1rm"] == 86.3
    nine = call(server, "training_estimate_1rm_from_rpe", weight_kg=100, reps=5, rpe=9)
    assert nine["percent_of_1rm"] == 83.7
    assert nine["estimated_1rm_kg"] == pytest.approx(119.5, abs=0.1)
    assert "error" in call(server, "training_estimate_1rm_from_rpe", weight_kg=100, reps=10, rpe=7)


def test_calorie_targets_match_mifflin_st_jeor_by_hand(server):
    out = call(server, "nutrition_estimate_targets", weight_kg=80, height_cm=180, age=30, sex="male", activity="moderate", goal="lose")
    assert out["bmr_kcal"] == 1780            # 10*80 + 6.25*180 - 5*30 + 5
    assert out["maintenance_kcal"] == 2759    # 1780 * 1.55
    assert out["targets"]["calories"] == 2207  # 20 percent deficit
    assert out["targets"]["protein_g"] == 160  # 2.0 g/kg while losing
    assert out["targets"]["fat_g"] >= 0.6 * 80


def test_calorie_targets_never_go_below_a_safe_floor(server):
    out = call(server, "nutrition_estimate_targets", weight_kg=45, height_cm=150, age=60, sex="female", activity="sedentary", goal="lose")
    assert out["targets"]["calories"] >= 1200
    assert any("1200" in n for n in out["notes"])


def test_readiness_gives_full_sleep_credit_at_seven_hours(server):
    seven = call(server, "recovery_calculate_readiness", sleep_hours=7, sleep_quality=10, soreness_1_10=1, stress_1_10=1)
    nine = call(server, "recovery_calculate_readiness", sleep_hours=9, sleep_quality=10, soreness_1_10=1, stress_1_10=1)
    assert seven["readiness_score"] == nine["readiness_score"] == 100.0
    assert call(server, "recovery_calculate_readiness", sleep_hours=5, sleep_quality=10, soreness_1_10=1, stress_1_10=1)["readiness_score"] < 100


def test_bad_numbers_return_an_error_not_a_wrong_answer(server):
    assert "error" in call(server, "training_log_set", exercise="squat", weight_kg=-5, reps=5)
    assert "error" in call(server, "training_log_set", exercise="squat", weight_kg=100, reps=0)
    assert "error" in call(server, "training_log_set", exercise="squat", weight_kg=100, reps=5, rpe=11)
    assert "error" in call(server, "recovery_log_sleep", hours=30, quality=5)
    assert "error" in call(server, "mental_log_mood", mood=11, energy=5, stress=5)
    assert "error" in call(server, "nutrition_log_meal", food_name="x", grams=100, calories=-1, protein_g=1, carbs_g=1, fat_g=1)
    assert check(x=(float("nan"), 0, 1)) is not None


def test_empty_database_results_are_labelled_as_sample_data(server):
    for name, args in [("training_get_prs", {}), ("recovery_get_sleep_trend", {}), ("mental_get_mood_trend", {}),
                       ("strongman_get_event_prs", {}), ("training_get_session_history", {"exercise": "squat"})]:
        out = call(server, name, **args)
        assert out["sample_data"] is True, name
        assert "made-up" in out["note"], name


def test_correlation_without_enough_data_is_not_invented(server):
    out = call(server, "mental_correlate_performance")
    assert out["status"] == "insufficient_data"
    assert "energy_vs_performance" not in out


def test_weekly_average_ignores_days_with_no_food_logged(server):
    today = date.today().isoformat()
    call(server, "nutrition_log_meal", food_name="meal", grams=100, calories=2000, protein_g=150, carbs_g=200, fat_g=60, date=today)
    out = call(server, "nutrition_get_weekly_macros")
    assert out["days_logged"] == 1
    assert out["7_day_avg"]["calories"] == 2000


def test_overreaching_does_not_count_the_unfinished_current_week(server):
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    if today.weekday() == 6:
        pytest.skip("On Sunday the current week counts as finished.")
    for weeks_back, weight in ((2, 100), (1, 100)):
        d = (this_monday - timedelta(weeks=weeks_back)).isoformat()
        call(server, "training_log_set", exercise="squat", weight_kg=weight, reps=5, rpe=7, date=d)
    # A light set today would make the current week look like a big drop if it were counted.
    call(server, "training_log_set", exercise="squat", weight_kg=40, reps=5, rpe=6, date=today.isoformat())
    out = call(server, "training_check_overreaching", exercise="squat", weeks=4)
    assert out["weeks_analyzed"] == 2
    assert out["risk"] == "low"


def test_readme_examples_show_real_tool_output(server):
    """The README quotes these numbers. If a formula changes, this fails until the README is updated."""
    from tests.helpers import REPO_ROOT

    readme = (REPO_ROOT / "README.md").read_text()
    wilks = call(server, "pl_calculate_wilks", bodyweight_kg=93, total_kg=570, sex="m")["wilks_score"]
    dots = call(server, "pl_calculate_dots", bodyweight_kg=93, total_kg=570, sex="m")["dots_score"]
    assert f"{wilks:.1f}" in readme and f"{dots:.1f}" in readme
    attempts = call(server, "pl_predict_attempts", squat_kg=200, bench_kg=130, deadlift_kg=240)
    for lift in ("squat", "bench", "deadlift"):
        a = attempts[lift]
        text = " / ".join(f"{a[k]:g}" for k in ("opener", "second", "third_pr"))
        assert text in readme, text
    readiness = call(server, "recovery_calculate_readiness", sleep_hours=6, sleep_quality=5, soreness_1_10=7, stress_1_10=7)
    assert f"{readiness['readiness_score']}" in readme
    targets = call(server, "nutrition_estimate_targets", weight_kg=80, height_cm=180, age=30, sex="male", activity="moderate", goal="lose")
    assert f"{targets['maintenance_kcal']} kcal" in readme and f"{targets['targets']['calories']} kcal" in readme
    assert "29 tools" in readme
