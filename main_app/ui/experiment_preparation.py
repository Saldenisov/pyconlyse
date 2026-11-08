"""Open the shared web experiment-preparation progress window."""

import os
from urllib.parse import urlencode

SUPPORTED_EXPERIMENTS = ("V0", "VD2")


def build_preparation_url(experiment: str, *, autostart: bool = True) -> str:
    """Build the local web URL used by both PyQt5 main windows."""
    selected = str(experiment or "").strip().upper()
    if selected not in SUPPORTED_EXPERIMENTS:
        raise ValueError(f"Unsupported experiment: {experiment}")
    base_url = os.environ.get("PYCONLYSE_WEB_URL", "http://127.0.0.1:5000").rstrip("/")
    query = {"experiment": selected}
    if autostart:
        query["autostart"] = "1"
    return f"{base_url}/experiment-preparation?{urlencode(query)}"


def open_preparation_window(experiment: str) -> bool:
    """Open the preparation UI in the operator's browser."""
    from PyQt5.QtCore import QUrl
    from PyQt5.QtGui import QDesktopServices

    return bool(QDesktopServices.openUrl(QUrl(build_preparation_url(experiment))))
