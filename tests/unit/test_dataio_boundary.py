"""Regression tests for the GUI-independent data reader boundary."""

import ast
import importlib
from pathlib import Path

import gui.controllers.openers as legacy_openers
from utilities import dataio


def _imported_modules(source: str):
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_treatment_service_uses_shared_dataio_not_gui_openers():
    service_path = Path(__file__).resolve().parents[2] / "web/backend/treatment_service.py"
    source = service_path.read_text(encoding="utf-8")
    imported = _imported_modules(source)

    assert "utilities.dataio" in imported
    assert all(not name.startswith("gui.controllers.openers") for name in imported)
    assert "gui.controllers.openers" not in source


def test_legacy_gui_openers_are_identity_reexports_of_shared_dataio():
    assert legacy_openers.ASCIIOpener is dataio.ASCIIOpener
    assert legacy_openers.H5Opener is dataio.H5Opener
    assert legacy_openers.HamamatsuFileOpener is dataio.HamamatsuFileOpener
    assert legacy_openers.Opener is dataio.Opener
    assert legacy_openers.CriticalInfo is dataio.CriticalInfo
    assert legacy_openers.CriticalInfoHamamatsu is dataio.CriticalInfoHamamatsu
    assert legacy_openers.OpenersTypes is dataio.OpenersTypes
    assert legacy_openers.OPENER_ACCRODANCE is dataio.OPENER_ACCRODANCE

    assert importlib.import_module(
        "gui.controllers.openers.ASCIIOpener"
    ).ASCIIOpener is dataio.ASCIIOpener
    assert legacy_openers.ASCIIOpener is dataio.ASCIIOpener
    assert importlib.import_module("gui.controllers.openers.H5Opener").H5Opener is dataio.H5Opener
    assert legacy_openers.H5Opener is dataio.H5Opener
    hamamatsu_module = importlib.import_module("gui.controllers.openers.HamamatsuFileOpener")
    assert hamamatsu_module.HamamatsuFileOpener is dataio.HamamatsuFileOpener
    assert hamamatsu_module.CriticalInfoHamamatsu is dataio.CriticalInfoHamamatsu
    assert legacy_openers.HamamatsuFileOpener is dataio.HamamatsuFileOpener
    assert legacy_openers.CriticalInfoHamamatsu is dataio.CriticalInfoHamamatsu
    opener_module = importlib.import_module("gui.controllers.openers.Opener")
    assert opener_module.Opener is dataio.Opener
    assert opener_module.CriticalInfo is dataio.CriticalInfo
    assert legacy_openers.Opener is dataio.Opener
    assert legacy_openers.CriticalInfo is dataio.CriticalInfo
