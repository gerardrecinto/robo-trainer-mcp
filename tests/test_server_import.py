def test_server_imports_and_registers_tools():
    from robo_trainer import server

    assert server.mcp is not None
    assert callable(server.main)
