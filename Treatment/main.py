"""Entry point for the standalone Treatment GUI project.

This module simply wires the repository root into ``sys.path`` and then
reuses the existing ``gui.Treatment.main`` entry point. This allows
running the Treatment GUI from a dedicated ``Treatment/`` project
without duplicating any of the core implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_repo_root_on_sys_path() -> Path:
    """Return the repository root and make sure it is first on ``sys.path``.

    The repo root is assumed to be the parent directory of this
    ``Treatment`` package, i.e. ``.../pyconlyse``.
    """

    repo_root = Path(__file__).resolve().parents[1]
    repo_str = str(repo_root)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)
    return repo_root


def main() -> int:
    """Run the Treatment GUI using the forked implementation under ``Treatment``."""

    _ensure_repo_root_on_sys_path()

    # Import lazily after sys.path has been adjusted
    from Treatment.treatment_gui.Treatment import main as treatment_main

    treatment_main()
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    raise SystemExit(main())
