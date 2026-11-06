"""Small per-browser/per-window UI snapshots. Contains no hardware operations."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3


def workspace_identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9-]{10,100}", value):
        raise ValueError("A browser/window workspace identity is required")
    return value


def validate_vd2_workspace(value):
    fields = {"outputRoot", "runName", "framesPerHis", "sampleDescription", "reuseBruit"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Only measurement form settings can be restored")
    result = {}
    for key, limit in [("outputRoot", 2048), ("runName", 200), ("sampleDescription", 4000)]:
        text = value[key]
        if not isinstance(text, str) or len(text) > limit or "\x00" in text:
            raise ValueError(f"Invalid {key}")
        result[key] = text
    # Drafts can be incomplete while the operator types; validation before an
    # acquisition remains authoritative. Restoring a draft never starts work.
    frames = value["framesPerHis"]
    if not isinstance(frames, str) or len(frames) > 6 or (frames and not frames.isascii()) or (frames and not frames.isdecimal()):
        raise ValueError("Invalid frame count draft")
    if value["reuseBruit"] not in {"latest", "none"}:
        raise ValueError("Invalid Noise Source")
    return {**result, "framesPerHis": frames, "reuseBruit": value["reuseBruit"]}


class WorkspaceConflict(ValueError):
    pass


class BrowserWorkspaceStates:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def _connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path), timeout=10)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS vd2_browser_workspaces (
                    browser_id TEXT NOT NULL, window_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, updated_at TEXT NOT NULL,
                    state_json TEXT NOT NULL, PRIMARY KEY(browser_id,window_id))""")
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _decode(row):
        return None if row is None else dict(window_id=row[0], revision=row[1], updated_at=row[2], settings=json.loads(row[3]))

    def get(self, browser, window):
        workspace_identity(browser); workspace_identity(window)
        with self._connection() as connection:
            return self._decode(connection.execute(
                "SELECT window_id,revision,updated_at,state_json FROM vd2_browser_workspaces WHERE browser_id=? AND window_id=?",
                (browser, window)).fetchone())

    def history(self, browser):
        workspace_identity(browser)
        with self._connection() as connection:
            return [self._decode(row) for row in connection.execute(
                "SELECT window_id,revision,updated_at,state_json FROM vd2_browser_workspaces WHERE browser_id=? ORDER BY updated_at DESC LIMIT 40",
                (browser,)).fetchall()]

    def save(self, browser, window, settings, revision):
        workspace_identity(browser); workspace_identity(window)
        settings = validate_vd2_workspace(settings)
        if type(revision) is not int or revision < 0:
            raise ValueError("Workspace revision is required")
        updated = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(settings, ensure_ascii=False, allow_nan=False)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT revision FROM vd2_browser_workspaces WHERE browser_id=? AND window_id=?", (browser, window)).fetchone()
            if (row[0] if row else 0) != revision:
                raise WorkspaceConflict("This window changed elsewhere. Reload its saved state before saving again.")
            connection.execute("""INSERT INTO vd2_browser_workspaces VALUES (?,?,?,?,?)
                ON CONFLICT(browser_id,window_id) DO UPDATE SET revision=excluded.revision,
                updated_at=excluded.updated_at,state_json=excluded.state_json""",
                (browser, window, revision + 1, updated, payload))
        return dict(window_id=window, revision=revision + 1, updated_at=updated, settings=settings)
