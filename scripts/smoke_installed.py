"""Smoke test for an installed copy of robo-trainer-mcp.

Run it with the Python that has the package installed, for example inside a fresh
virtual environment that only ran `pip install robo_trainer_mcp-*.whl`:

    python scripts/smoke_installed.py
"""
import json
import os
import subprocess
import sys
import tempfile

EXPECTED_TOOL_COUNT = 29


def main() -> int:
    with tempfile.TemporaryDirectory() as home:
        env = {**os.environ, "ROBO_TRAINER_HOME": home}
        proc = subprocess.Popen(
            [sys.executable, "-m", "robo_trainer.server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )

        def rpc(msg):
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline()) if "id" in msg else None

        try:
            init = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}}})
            rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        except Exception:
            proc.kill()
            print(proc.stderr.read(), file=sys.stderr)
            raise
        finally:
            proc.kill()
        count = len(tools["result"]["tools"])
        print(f"server {init['result']['serverInfo']['name']} answered, {count} tools")
        if count != EXPECTED_TOOL_COUNT:
            print(f"expected {EXPECTED_TOOL_COUNT} tools", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
