import pytest

from tests._tango_stub import install_tango_stub
from scripts.refactor.pytest_module_isolation import isolated_test_modules


pytest_plugins = ("scripts.refactor.pytest_module_isolation",)


@pytest.fixture(autouse=True)
def isolated_tango_stub(monkeypatch):
    """Provide Tango only for one test and undo it during fixture teardown."""
    with isolated_test_modules():
        install_tango_stub(monkeypatch)
        yield
