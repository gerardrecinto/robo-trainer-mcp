# Contributing

Small, focused pull requests are easiest to review.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests scripts
pytest
npm ci && npm test        # website tests, needs Node 22
```

Before you open a pull request:

- Add or update a test. Tests that start the real server are in `tests/test_integration.py` and `tests/test_stdio_e2e.py`.
- If you change a formula, say where the method comes from and add a test with a value worked out by hand or from a published example.
- If you add or remove a tool, update the golden list in `tests/helpers.py` and the tool count in `scripts/smoke_installed.py`.
- The README quotes real tool output. `tests/test_accuracy.py` fails if those numbers drift.

Pull requests squash-merge once the `CI gate` check passes.
