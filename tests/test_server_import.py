def test_server_imports_and_builds(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBO_TRAINER_HOME", str(tmp_path))
    from robo_trainer import server

    assert callable(server.main)
    assert server.create_server() is not None
