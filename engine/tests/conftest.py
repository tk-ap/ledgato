"""Test tiering for the enforcement stress test.

Three tiers, deliberately kept apart (directive stage 8):

* **unit** (default) — in-process fakes only. Safe anywhere, runs in CI.
* **live** — talks to a real provider with a real credential. Opt-in only.
* **sandbox** — needs bubblewrap on the host.

Live tests are skipped unless BOTH are true: ``LEDGATO_LIVE_TESTS=1`` is set,
and the required credential/repo variables are present. That is enforced here
rather than through ``addopts`` because CI invokes ``pytest -q engine/tests``
from the repository root, where this package's pyproject may not be picked up
as the config source — a marker expression left in pyproject could silently
stop applying and let live tests fire in CI against a real repository.
"""
import os
import shutil

import pytest

LIVE_ENV_FLAG = "LEDGATO_LIVE_TESTS"
LIVE_REQUIRED_VARS = ("LEDGATO_GITHUB_TOKEN", "LEDGATO_GITHUB_REPOSITORY")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: needs a real provider credential; opt-in")
    config.addinivalue_line("markers", "sandbox: needs bubblewrap on the host")


def live_tests_enabled() -> tuple[bool, str]:
    if os.getenv(LIVE_ENV_FLAG) != "1":
        return False, f"live provider tests are opt-in: set {LIVE_ENV_FLAG}=1"
    missing = [v for v in LIVE_REQUIRED_VARS if not os.getenv(v)]
    if missing:
        return False, f"missing live provider config: {', '.join(missing)}"
    return True, ""


def pytest_collection_modifyitems(config, items):
    live_ok, live_reason = live_tests_enabled()
    have_bwrap = shutil.which("bwrap") is not None

    for item in items:
        if "live" in item.keywords and not live_ok:
            item.add_marker(pytest.mark.skip(reason=live_reason))
        if "sandbox" in item.keywords and not have_bwrap:
            item.add_marker(pytest.mark.skip(reason="bubblewrap (bwrap) not installed"))


@pytest.fixture(scope="session")
def live_repository() -> str:
    """The disposable lab repository. Refuses anything that looks like production.

    A live test that accidentally points at a product repository would violate
    the directive's first safety boundary, so the guard is here rather than in
    each test.
    """
    repo = os.getenv("LEDGATO_GITHUB_REPOSITORY", "")
    forbidden = ("ledgato", "ailhat", "alvira", "agent-os", "ashwood")
    name = repo.split("/")[-1].lower()
    if name in forbidden:
        pytest.fail(
            f"refusing to run live tests against '{repo}': this looks like a "
            "production repository. Use a disposable lab repo."
        )
    if "lab" not in name and "test" not in name:
        pytest.fail(
            f"refusing to run live tests against '{repo}': the repository name "
            "must identify it as a disposable lab (contain 'lab' or 'test')."
        )
    return repo
