import os

import pytest

from tests._tango_stub import install_tango_stub
from scripts.refactor.pytest_network_guard import install_network_guard
from scripts.refactor.pytest_module_isolation import isolated_test_modules


pytest_plugins = ("scripts.refactor.pytest_module_isolation",)


def pytest_addoption(parser):
    parser.addoption(
        "--deny-network",
        action="store_true",
        default=False,
        help="Block external DNS, TCP, and UDP in the software-only lane.",
    )


def pytest_configure(config):
    enabled = config.getoption("--deny-network") or os.environ.get(
        "PYCONLYSE_DENY_NETWORK"
    ) == "1"
    if not enabled:
        return
    guard = pytest.MonkeyPatch()
    guard.setenv("PYCONLYSE_DENY_NETWORK", "1")
    install_network_guard(guard)
    guard.setenv("PYCONLYSE_NETWORK_GUARD_ACTIVE", "1")
    config._pyconlyse_network_guard = guard


def pytest_unconfigure(config):
    guard = getattr(config, "_pyconlyse_network_guard", None)
    if guard is not None:
        guard.undo()


@pytest.fixture(autouse=True)
def isolated_tango_stub(monkeypatch):
    """Provide Tango only for one test and undo it during fixture teardown."""
    with isolated_test_modules():
        install_tango_stub(monkeypatch)
        yield
