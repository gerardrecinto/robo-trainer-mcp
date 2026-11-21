import json
import os
import stat

import pytest

from robo_trainer import db, export


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path / "home"))
    db.init_db()
    with db.get_conn() as conn:
        conn.execute("INSERT INTO bodyweight_log (date, weight_kg) VALUES ('2026-11-01', 82.5)")
        conn.execute("INSERT INTO bodyweight_log (date, weight_kg) VALUES ('2026-11-02', 82.1)")
    return tmp_path


def test_export_writes_every_table_and_counts_rows(home, capsys):
    out = home / "out.json"
    assert export.main([str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["row_counts"]["bodyweight_log"] == 2
    assert {"food_log", "training_log", "sleep_log", "mood_log", "training_plan"} <= set(doc["tables"])
    assert [r["weight_kg"] for r in doc["tables"]["bodyweight_log"]] == [82.5, 82.1]
    total = sum(doc["row_counts"].values())
    assert f"{total} rows from {len(doc['tables'])} tables" in capsys.readouterr().out


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_export_file_is_private(home):
    out = home / "out.json"
    export.main([str(out)])
    assert stat.S_IMODE(out.stat().st_mode) == 0o600


def test_refuses_to_overwrite_without_force(home, capsys):
    out = home / "out.json"
    out.write_text("keep me")
    assert export.main([str(out)]) == 1
    assert out.read_text() == "keep me" and "--force" in capsys.readouterr().err
    assert export.main([str(out), "--force"]) == 0
    assert json.loads(out.read_text())["row_counts"]


def test_missing_database_is_named_and_not_created(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path / "nothing"))
    assert export.main([str(tmp_path / "o.json")]) == 1
    assert "ROBO_TRAINER_HOME" in capsys.readouterr().err
    assert not (tmp_path / "nothing").exists()


def test_export_does_not_change_the_database(home):
    before = db.db_path().read_bytes()
    export.main([str(home / "o.json")])
    assert db.db_path().read_bytes() == before


def test_bad_arguments_exit_2(home, capsys):
    assert export.main(["--bogus"]) == 2
    assert export.main(["a.json", "b.json"]) == 2
    assert "usage:" in capsys.readouterr().err
