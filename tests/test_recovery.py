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

    class _Conn:
        def execute(self, *a, **kw): return self
        def fetchone(self): return None
        def fetchall(self): return []

    @contextmanager
    def get_conn(*a, **kw): yield _Conn()

    db.get_conn = get_conn
    db.init_db = lambda *a, **kw: None
    sys.modules["robo_trainer.db"] = db


def _fresh_recovery():
    _stub_db()
    sys.modules.pop("robo_trainer.tools.recovery", None)
    return importlib.import_module("robo_trainer.tools.recovery")


def test_readiness_high():
    recovery = _fresh_recovery()
    mcp = _FakeMCP()
    recovery.register(mcp, lambda t, p: None)
    result = json.loads(mcp.tools["recovery_calculate_readiness"](
        sleep_hours=9.0, sleep_quality=9, soreness_1_10=2, stress_1_10=2
    ))
    assert result["readiness_score"] >= 80
    assert "push intensity" in result["recommendation"]


def test_readiness_low():
    recovery = _fresh_recovery()
    mcp = _FakeMCP()
    recovery.register(mcp, lambda t, p: None)
    result = json.loads(mcp.tools["recovery_calculate_readiness"](
        sleep_hours=4.0, sleep_quality=3, soreness_1_10=9, stress_1_10=9
    ))
    assert result["readiness_score"] < 40
    assert "rest day" in result["recommendation"]


def test_readiness_mid():
    recovery = _fresh_recovery()
    mcp = _FakeMCP()
    recovery.register(mcp, lambda t, p: None)
    result = json.loads(mcp.tools["recovery_calculate_readiness"](
        sleep_hours=7.0, sleep_quality=6, soreness_1_10=5, stress_1_10=5
    ))
    assert 40 <= result["readiness_score"] < 80
