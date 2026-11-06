"""Assemble the GitHub Pages site into a folder: python3 scripts/assemble_site.py _site

The Pages workflow and the site tests both call this, so what the tests check is what ships.
"""
import ast
import glob
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The in-browser demo runs the real powerlifting tools in Pyodide. Every module they import
# has to be listed here, or the demo breaks on the live site.
PYTHON_FILES = ["__init__.py", "validation.py", "formulas.py", "tools/__init__.py", "tools/powerlifting.py"]


def tool_list(tools_dir: Path) -> list[dict]:
    tools, seen = [], set()
    for f in sorted(glob.glob(os.path.join(tools_dir, "*.py"))):
        service = os.path.basename(f)[:-3]
        if service.startswith("_"):
            continue
        for node in ast.walk(ast.parse(open(f).read())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any("tool" in ast.dump(d) for d in node.decorator_list):
                if node.name in seen:
                    continue
                seen.add(node.name)
                doc = (ast.get_docstring(node) or "").split("\n")[0]
                args = [a.arg for a in node.args.args if a.arg != "self"]
                tools.append({"name": node.name, "service": service, "doc": doc, "args": args})
    return tools


def main(out: str) -> None:
    site = Path(out)
    if site.exists():
        shutil.rmtree(site)
    (site / "py" / "tools").mkdir(parents=True)
    shutil.copy(ROOT / "site" / "index.html", site / "index.html")
    for name in PYTHON_FILES:
        shutil.copy(ROOT / "src" / "robo_trainer" / name, site / "py" / name)
    tools = tool_list(ROOT / "src" / "robo_trainer" / "tools")
    (site / "tools.json").write_text(json.dumps(tools, indent=1))
    (site / ".nojekyll").touch()
    print(len(tools), "tools")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "_site")
