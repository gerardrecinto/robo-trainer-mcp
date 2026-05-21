from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP(
    "robo-trainer",
    description=(
        "Full-stack personal trainer MCP: nutrition, strength training, "
        "powerlifting, strongman, recovery, and mental performance coaching."
    ),
)

_audit_path: Path | None = None


def _init_audit() -> None:
    global _audit_path
    log_dir = Path.home() / ".robo-trainer"
    log_dir.mkdir(parents=True, exist_ok=True)
    _audit_path = log_dir / "audit.log"


def _audit(tool: str, params: dict[str, Any]) -> None:
    if _audit_path is None:
        return
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "tool": tool, "params": params}
    with open(_audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    _init_audit()
    from robo_trainer.tools import nutrition, training, powerlifting, strongman, recovery, mental_health
    nutrition.register(mcp, _audit)
    training.register(mcp, _audit)
    powerlifting.register(mcp, _audit)
    strongman.register(mcp, _audit)
    recovery.register(mcp, _audit)
    mental_health.register(mcp, _audit)
    mcp.run()


if __name__ == "__main__":
    main()
