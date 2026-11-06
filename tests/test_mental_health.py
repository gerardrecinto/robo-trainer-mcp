import importlib
import json
import sys
import types
from contextlib import contextmanager


class _FakeMCP:
    def __init__(self): self.tools = {}
    def tool(self):
        def dec(fn): self.tools[fn.__name__] = fn; return fn
        return dec


def _fresh(mood_rows=(), train_rows=()):
    db = types.ModuleType("robo_trainer.db")

    class _Conn:
        def execute(self, sql, *a, **kw):
            self.sql = sql
            return self
        def fetchall(self):
            return list(mood_rows) if "mood_log" in self.sql else list(train_rows)
        def fetchone(self): return None

    @contextmanager
    def get_conn(*a, **kw): yield _Conn()

    db.get_conn = get_conn
    db.init_db = lambda *a, **kw: None
    sys.modules["robo_trainer.db"] = db
    sys.modules.pop("robo_trainer.tools.mental_health", None)
    return importlib.import_module("robo_trainer.tools.mental_health")


def test_direction_follows_the_sign_of_r():
    mh = _fresh()
    assert mh._interpret_r(-0.58) == "Moderate negative correlation (r=-0.58)"
    assert mh._interpret_r(0.71) == "Strong positive correlation (r=0.71)"
    assert mh._interpret_r(0.25) == "Weak positive correlation (r=0.25)"
    assert mh._interpret_r(-0.25) == "Weak negative correlation (r=-0.25)"
    assert mh._interpret_r(0.1) == "No meaningful correlation detected"
    assert mh._interpret_r(-0.1) == "No meaningful correlation detected"


def test_stress_that_lowers_performance_is_reported_as_negative():
    # Stress rises while the top-set estimate falls; energy falls with it.
    days = [f"2026-11-0{i}" for i in range(1, 7)]
    stress = [2, 3, 4, 5, 6, 8]
    energy = [9, 8, 7, 6, 5, 3]
    perf = [140.0, 135.0, 130.0, 120.0, 115.0, 100.0]
    mood = [{"date": d, "energy": e, "stress": s} for d, e, s in zip(days, energy, stress, strict=True)]
    train = [{"date": d, "top_1rm": p} for d, p in zip(days, perf, strict=True)]
    mh = _fresh(mood, train)
    mcp = _FakeMCP()
    mh.register(mcp, lambda t, p: None)
    out = json.loads(mcp.tools["mental_correlate_performance"]())
    assert out["stress_vs_performance"]["pearson_r"] < -0.7
    assert out["stress_vs_performance"]["interpretation"].startswith("Strong negative correlation")
    assert out["energy_vs_performance"]["pearson_r"] > 0.7
    assert out["energy_vs_performance"]["interpretation"].startswith("Strong positive correlation")
    assert "Higher stress days tend to line up with weaker sets" in out["insight"]
    assert out["confidence"] == "low"

