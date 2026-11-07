from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from robo_trainer.db import data_dir

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Local training and nutrition log, calculators and plan generator for lifters and general fitness. "
    "General fitness information, not medical advice."
)

_audit_path: Path | None = None


def _init_audit() -> None:
    global _audit_path
    log_dir = data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    _audit_path = log_dir / "audit.log"


def _audit(tool: str, params: dict[str, Any]) -> None:
    if _audit_path is None:
        return
    entry = {"ts": datetime.now(UTC).isoformat(), "tool": tool, "params": params}
    with open(_audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def create_server() -> FastMCP:
    """Build a server with every tool module registered."""
    _init_audit()
    from robo_trainer.tools import mental_health, nutrition, planning, powerlifting, recovery, strongman, training

    server = FastMCP("robo-trainer", instructions=INSTRUCTIONS)
    registered: list[str] = []
    for mod in (nutrition, training, powerlifting, strongman, recovery, mental_health, planning):
        name = mod.__name__.split(".")[-1]
        mod.register(server, _audit)
        registered.append(name)
    logger.info("robo-trainer started, registered: %s", ", ".join(registered))
    return server


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
