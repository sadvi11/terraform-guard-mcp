"""Point the guard at this repository's fixture plans, wherever pytest runs.

tfguard resolves plans against TFGUARD_PLAN_DIR, defaulting to ./plans - which
is correct for the server, since you run it against your own plan directory.
It made the tests depend on the working directory though: they passed from the
repo root and failed from anywhere else, including from a directory where the
package had been pip-installed.

That is the same shape as the bug this project exists to catch - something that
works in the one place it is usually run and fails everywhere else - so it is
worth not having in its own test suite.
"""
from __future__ import annotations

import os
import pathlib

import pytest

PLANS = pathlib.Path(__file__).resolve().parent.parent / "plans"


@pytest.fixture(autouse=True, scope="session")
def _plan_dir():
    previous = os.environ.get("TFGUARD_PLAN_DIR")
    os.environ["TFGUARD_PLAN_DIR"] = str(PLANS)

    # tfguard.plan reads the variable once at import time, so the module-level
    # constant has to be refreshed too - setting the variable alone would look
    # like it worked and change nothing.
    from tfguard import plan as plan_mod
    original = plan_mod.PLAN_DIR
    plan_mod.PLAN_DIR = PLANS.resolve()
    yield
    plan_mod.PLAN_DIR = original
    if previous is None:
        os.environ.pop("TFGUARD_PLAN_DIR", None)
    else:
        os.environ["TFGUARD_PLAN_DIR"] = previous
