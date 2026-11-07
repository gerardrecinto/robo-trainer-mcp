import os
import stat

from robo_trainer import server


def test_audit_log_rotates_and_stays_private(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path))
    monkeypatch.setenv("ROBO_TRAINER_AUDIT_MAX_BYTES", "200")
    server._init_audit()
    for i in range(20):
        server._audit("tool", {"n": i, "pad": "x" * 40})
    log = tmp_path / "audit.log"
    old = tmp_path / "audit.log.1"
    assert old.exists()
    assert log.stat().st_size < 400
    assert old.stat().st_size < 400
    for f in (log, old):
        if os.name == "posix":
            assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_bad_limit_does_not_break_logging(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path))
    monkeypatch.setenv("ROBO_TRAINER_AUDIT_MAX_BYTES", "not-a-number")
    server._init_audit()
    server._audit("tool", {})
    assert (tmp_path / "audit.log").read_text().count("\n") == 1
