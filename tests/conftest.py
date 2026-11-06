import sys

import pytest


@pytest.fixture
def no_audit():
    return lambda tool, params: None


@pytest.fixture(autouse=True)
def isolate_robo_trainer_modules():
    """Some unit tests stub robo_trainer.db. Put the module table back after every test
    so the integration tests always see the real code."""
    before = {k: v for k, v in sys.modules.items() if k.startswith("robo_trainer")}
    yield
    for name in [k for k in sys.modules if k.startswith("robo_trainer")]:
        if name in before:
            sys.modules[name] = before[name]
        else:
            del sys.modules[name]
