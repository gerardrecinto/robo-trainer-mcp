"""Start the server as a real subprocess and speak MCP over stdio, the way a client does."""
import json
import os
import subprocess
import sys

from tests.helpers import EXPECTED_TOOLS


def _rpc(proc, message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()
    if "id" not in message:
        return None
    return json.loads(proc.stdout.readline())


def run_stdio_session(command, env, timeout=60):
    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, env=env,
    )
    try:
        init = _rpc(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "e2e", "version": "0"}},
        })
        _rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        call = _rpc(proc, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "training_calculate_1rm", "arguments": {"weight_kg": 100, "reps": 5}},
        })
        return init, tools, call
    finally:
        proc.kill()
        proc.wait(timeout=timeout)


def test_server_starts_and_answers_over_stdio(tmp_path):
    env = {**os.environ, "ROBO_TRAINER_HOME": str(tmp_path)}
    init, tools, call = run_stdio_session([sys.executable, "-m", "robo_trainer.server"], env)
    assert init["result"]["serverInfo"]["name"] == "robo-trainer"
    assert {t["name"] for t in tools["result"]["tools"]} == EXPECTED_TOOLS
    assert len(tools["result"]["tools"]) == 36
    payload = json.loads(call["result"]["content"][0]["text"])
    assert payload["estimated_1rm_kg"] == 116.7
