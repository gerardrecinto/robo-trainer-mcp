from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

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
    modules = [nutrition, training, powerlifting, strongman, recovery, mental_health]
    registered: list[str] = []
    for mod in modules:
        name = mod.__name__.split(".")[-1]
        try:
            mod.register(mcp, _audit)
            registered.append(name)
        except Exception as exc:
            logger.warning("tool module %s failed to load: %s", name, exc)
    logger.info("robo-trainer started — registered: %s", ", ".join(registered))
    mcp.run()


if __name__ == "__main__":
    main()
