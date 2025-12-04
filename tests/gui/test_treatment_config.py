"""Tests for the Treatment GUI configuration helper.

These tests only cover the pure-Python configuration logic and do not
invoke any Qt components, so they are safe to run in headless CI.
"""

from pathlib import Path
from typing import Dict

import os

from gui import treatment_config


def _with_env(vars: Dict[str, str]):
    """Context manager-like helper for temporarily setting env vars.

    Implemented as a generator function so we don't depend on pytest
    context managers and can keep the code very small and explicit.
    """

    old_values = {k: os.environ.get(k) for k in vars}
    try:
        os.environ.update(vars)
        yield
    finally:
        for k, v in old_values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_default_data_folder_when_env_not_set():
    """If TREATMENT_DATA_DIR is not set, use DEFAULT_DATA_FOLDER (E:/ by default)."""

    # Ensure the env var is not present for this test
    env_name = "TREATMENT_DATA_DIR"
    old = os.environ.pop(env_name, None)
    try:
        data_folder = treatment_config.get_data_folder()
        assert isinstance(data_folder, Path)
        assert data_folder == treatment_config.DEFAULT_DATA_FOLDER
    finally:
        if old is not None:
            os.environ[env_name] = old


def test_data_folder_can_be_overridden_via_environment():
    """TREATMENT_DATA_DIR environment variable should override the default."""

    env_name = "TREATMENT_DATA_DIR"
    override_path = str(Path("C:/tmp/treatment_data"))
    old = os.environ.get(env_name)
    try:
        os.environ[env_name] = override_path
        data_folder = treatment_config.get_data_folder()
        assert data_folder == Path(override_path)
    finally:
        # Restore original value
        if old is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = old
