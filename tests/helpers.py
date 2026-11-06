"""Shared helpers for tests that run the real server."""
import asyncio
import json
import sys
from pathlib import Path

EXPECTED_TOOLS = {
    "mental_correlate_performance", "mental_get_mood_trend", "mental_log_mood",
    "nutrition_get_daily_summary", "nutrition_get_weekly_macros", "nutrition_log_meal",
    "nutrition_search_food", "nutrition_set_goals", "nutrition_estimate_targets",
    "pl_analyze_sbd_ratio", "pl_calculate_dots", "pl_calculate_wilks", "pl_predict_attempts",
    "recovery_calculate_readiness", "recovery_get_sleep_trend", "recovery_log_sleep",
    "strongman_competition_standards", "strongman_get_event_history",
    "strongman_get_event_prs", "strongman_log_event",
    "training_calculate_1rm", "training_check_overreaching", "training_get_bodyweight_trend",
    "training_get_prs", "training_get_session_history", "training_get_volume_trend",
    "training_log_bodyweight", "training_log_set", "training_estimate_1rm_from_rpe",
}


def purge_robo_trainer() -> None:
    for name in [k for k in sys.modules if k.startswith("robo_trainer")]:
        del sys.modules[name]


def call(server, name: str, **arguments):
    """Call a tool through the real MCP server and return the decoded JSON."""
    result = asyncio.run(server.call_tool(name, arguments))
    blocks = result[0] if isinstance(result, tuple) else result
    return json.loads(blocks[0].text)


def tool_names(server) -> set[str]:
    return {t.name for t in asyncio.run(server.list_tools())}


REPO_ROOT = Path(__file__).resolve().parents[1]
