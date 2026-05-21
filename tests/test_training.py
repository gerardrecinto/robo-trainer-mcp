import json
import sys
import types
import importlib
from contextlib import contextmanager


class _FakeMCP:
    def __init__(self): self.tools = {}
    def tool(self):
        def dec(fn): self.tools[fn.__name__] = fn; return fn
        return dec


def _stub_db():
    db = types.ModuleType("robo_trainer.db")

    class _Row(dict):
        def __missing__(self, k): return None

    class _Conn:
        def execute(self, *a, **kw): return self
        def fetchone(self): return _Row(n=0, weight_kg=180.0, reps=3, date="2024-01-10")
        def fetchall(self): return []

    @contextmanager
    def get_conn(*a, **kw): yield _Conn()

    db.get_conn = get_conn
    db.init_db = lambda *a, **kw: None
    sys.modules["robo_trainer.db"] = db


def _fresh_training():
    _stub_db()
    sys.modules.pop("robo_trainer.tools.training", None)
    return importlib.import_module("robo_trainer.tools.training")


def test_epley_1rm_single():
    training = _fresh_training()
    assert training._epley_1rm(200.0, 1) == 200.0


def test_epley_1rm_reps():
    """Epley: 180 kg x 5 reps -> ~210 kg estimated 1RM."""
    training = _fresh_training()
    result = training._epley_1rm(180.0, 5)
    assert 205 < result < 215


def test_volume_trend_returns_demo_when_no_data():
    training = _fresh_training()
    mcp = _FakeMCP()
    training.register(mcp, lambda t, p: None)
    result = json.loads(mcp.tools["training_get_volume_trend"](exercise="squat", weeks=4))
    assert result["exercise"] == "squat"
    assert len(result["trend"]) == 4
    for week in result["trend"]:
        assert week["volume_kg"] > 0
