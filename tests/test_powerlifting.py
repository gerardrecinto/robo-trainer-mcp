import json
import sys
import importlib


class _FakeMCP:
    def __init__(self): self.tools = {}
    def tool(self):
        def dec(fn): self.tools[fn.__name__] = fn; return fn
        return dec


def _pl():
    sys.modules.pop("robo_trainer.tools.powerlifting", None)
    return importlib.import_module("robo_trainer.tools.powerlifting")


def test_wilks_known_value():
    """93 kg male, 570 kg total -> Wilks should be in the Advanced range."""
    pl = _pl()
    mcp = _FakeMCP()
    pl.register(mcp, lambda t, p: None)
    result = json.loads(mcp.tools["pl_calculate_wilks"](bodyweight_kg=93.0, total_kg=570.0, sex="m"))
    assert 300 < result["wilks_score"] < 500
    assert result["classification"] in ("Advanced", "Master", "Intermediate")


def test_dots_known_value():
    pl = _pl()
    mcp = _FakeMCP()
    pl.register(mcp, lambda t, p: None)
    result = json.loads(mcp.tools["pl_calculate_dots"](bodyweight_kg=83.0, total_kg=500.0, sex="m"))
    assert result["dots_score"] > 0
    assert "classification" in result


def test_sbd_ratio_identifies_bench_weakness():
    """S=200, B=120, D=240 -> bench is furthest below its elite proportion."""
    pl = _pl()
    mcp = _FakeMCP()
    pl.register(mcp, lambda t, p: None)
    result = json.loads(mcp.tools["pl_analyze_sbd_ratio"](squat_kg=200.0, bench_kg=120.0, deadlift_kg=240.0))
    assert result["weakest_lift"] == "bench"


def test_attempt_prediction():
    pl = _pl()
    mcp = _FakeMCP()
    pl.register(mcp, lambda t, p: None)
    result = json.loads(mcp.tools["pl_predict_attempts"](squat_kg=200.0, bench_kg=130.0, deadlift_kg=240.0))
    assert result["squat"]["opener"] < result["squat"]["third_pr"]
    assert result["bench"]["opener"] < 130.0
    assert result["projected_total_kg"] > 0
