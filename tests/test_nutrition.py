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
        def __missing__(self, k): return 0

    class _Conn:
        def execute(self, *a, **kw): return self
        def fetchone(self): return _Row(cal=0, prot=0, carbs=0, fat=0, calories=2500, protein_g=180, carbs_g=300, fat_g=80)
        def fetchall(self): return []

    @contextmanager
    def get_conn(*a, **kw): yield _Conn()

    db.get_conn = get_conn
    db.init_db = lambda *a, **kw: None
    sys.modules["robo_trainer.db"] = db


def _fresh_nutrition():
    _stub_db()
    sys.modules.pop("robo_trainer.tools.nutrition", None)
    return importlib.import_module("robo_trainer.tools.nutrition")


def test_demo_search_returns_results():
    """_demo_food_search fallback returns items with positive protein values."""
    nutrition = _fresh_nutrition()
    result = nutrition._demo_food_search("chicken")
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["per_100g"]["protein_g"] > 0


def test_demo_search_uses_query_name():
    nutrition = _fresh_nutrition()
    result = nutrition._demo_food_search("rice")
    assert any("Rice" in item["name"] for item in result)
