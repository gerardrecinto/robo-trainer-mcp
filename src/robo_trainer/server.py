from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from robo_trainer.db import data_dir, make_private

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Local training and nutrition log, calculators and plan generator for lifters and general fitness. "
    "General fitness information, not medical advice."
)

AUDIT_MAX_BYTES = 5_000_000

_audit_path: Path | None = None


def _init_audit() -> None:
    global _audit_path
    log_dir = data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    _audit_path = log_dir / "audit.log"
    _audit_path.touch(exist_ok=True)
    make_private(log_dir)
    make_private(_audit_path)


def _audit(tool: str, params: dict[str, Any]) -> None:
    if _audit_path is None:
        return
    entry = {"ts": datetime.now(UTC).isoformat(), "tool": tool, "params": params}
    _rotate_audit(_audit_path)
    with open(_audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    make_private(_audit_path)


def _rotate_audit(path: Path) -> None:
    """Keep one previous log so the file cannot grow without limit."""
    try:
        limit = int(os.environ.get("ROBO_TRAINER_AUDIT_MAX_BYTES", AUDIT_MAX_BYTES))
        if limit > 0 and path.stat().st_size >= limit:
            os.replace(path, path.with_name(path.name + ".1"))
    except (OSError, ValueError):
        logger.warning("could not rotate the audit log", exc_info=True)


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
