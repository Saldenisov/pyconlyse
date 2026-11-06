"""Durable camera return points. No Tango imports, process or acquisition I/O."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from vd2_dg645_timing import timing_for_range

# Deliberately excludes shutters, power, raw delays, magnets and motor positions.
PARAMETERS = {
    "time_range": "DevParamGet(TD,Time Range)",
    "streak_mode": "DevParamGet(TD,Mode)",
    "mcp_gain": "DevParamGet(TD,MCP Gain)",
    "wavelength_nm": "DevParamGet(Spec,Wavelength)",
    "slit_width_um": "DevParamGet(Spec,Slit Width)",
    "live_exposure_time": "CamParamGet(Live,Exposure)",
    "acquire_exposure_time": "CamParamGet(Acquire,Exposure)",
    "analog_integration_count": "CamParamGet(AI,NrExposures)",
    "sequence_loops": "SeqParamGet(NoOfLoops)",
}


def validate_settings(values):
    if not isinstance(values, dict) or set(values) - (set(PARAMETERS) | {"rolling_average"}):
        raise ValueError("Invalid camera return point")
    if not {"time_range", "streak_mode"} <= set(values):
        raise ValueError("Camera mode and calibrated time range are required")
    result = {}
    for name, value in values.items():
        if name == "rolling_average":
            if (not isinstance(value, dict) or set(value) != {"enabled", "frames"}
                    or type(value["enabled"]) is not bool or type(value["frames"]) is not int
                    or not 2 <= value["frames"] <= 255):
                raise ValueError("Invalid saved rolling average")
            result[name] = dict(value)
            continue
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"Invalid saved {name}")
        text = str(value).strip()
        if not text or len(text) > 64 or not re.fullmatch(r"[\w .+µμ-]+", text):
            raise ValueError(f"Invalid saved {name}")
        if name == "time_range":
            text = timing_for_range(text).time_range
        elif name == "streak_mode":
            if text.lower() not in {"focus", "operate"}:
                raise ValueError("Unsupported saved camera mode")
            text = text.capitalize()
        elif name in {"mcp_gain", "wavelength_nm", "slit_width_um", "analog_integration_count", "sequence_loops"}:
            number = float(text)
            if not math.isfinite(number) or number < 0:
                raise ValueError(f"Invalid saved {name}")
            if name == "mcp_gain" and (number > 255 or not number.is_integer()):
                raise ValueError("Invalid saved gain")
            if name in {"analog_integration_count", "sequence_loops"} and (number < 1 or not number.is_integer()):
                raise ValueError(f"Invalid saved {name}")
            if name == "wavelength_nm" and number <= 0:
                raise ValueError("Invalid saved wavelength")
            if name == "slit_width_um" and number == 0:
                # The streak Tango server returns zero when no slit width is available.
                continue
            text = format(number, ".12g")
        elif name in {"live_exposure_time", "acquire_exposure_time"}:
            if not re.fullmatch(r"\d+(?:\.\d+)?\s*(?:ns|us|µs|μs|ms|s)", text, re.I):
                raise ValueError(f"Explicit exposure units are required for {name}")
        result[name] = text
    return result


def settings_from_state(state, average=None):
    if not state.get("connected") or not state.get("application_running"):
        raise ValueError("Disconnected camera cannot replace a return point")
    values, errors = state.get("values", {}), state.get("attribute_errors", {})
    if any(name in errors for name in PARAMETERS):
        raise ValueError("Incomplete camera readback cannot replace a return point")
    # Missing optional attributes stay explicitly absent; never invent defaults.
    settings = {name: values[name] for name in PARAMETERS if values.get(name) not in (None, "")}
    if average is not None:
        settings["rolling_average"] = average
    return validate_settings(settings)


def equivalent(name, expected, actual):
    try:
        settings = validate_settings({"time_range": "1 us", "streak_mode": "Operate", name: actual})
        return settings.get(name) == expected
    except (ValueError, TypeError):
        return False


class RecoverySnapshots:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path), timeout=5)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                connection.execute("CREATE TABLE IF NOT EXISTS vd2_camera_return_points (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS vd2_camera_return_heads (kind TEXT PRIMARY KEY, id TEXT NOT NULL)")
                yield connection
        finally:
            connection.close()

    def capture(self, settings, kind="previous", ui=None):
        if kind not in {"previous", "alignment", "point"}:
            raise ValueError("Invalid camera return point kind")
        settings = validate_settings(settings)
        ui = ui or {"tab": "alignment" if kind == "alignment" else "acquisition"}
        if not isinstance(ui, dict) or set(ui) - {"tab", "form"} or ui.get("tab") not in {"acquisition", "alignment"}:
            raise ValueError("Invalid return point interface")
        if "form" in ui:
            from browser_workspace_state import validate_vd2_workspace
            ui = {**ui, "form": validate_vd2_workspace(ui["form"])}
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT value FROM vd2_camera_return_points JOIN vd2_camera_return_heads USING(id) WHERE kind=?", (kind,)).fetchone()
            old = json.loads(row[0]) if row else None
            if old and old["settings"] == settings and old["ui"] == ui:
                snapshot = old
            else:
                snapshot = dict(id=uuid4().hex, created_at=datetime.now(timezone.utc).isoformat(),
                                settings=settings, ui=ui, kind=kind)
                connection.execute("INSERT INTO vd2_camera_return_points VALUES (?,?)", (snapshot["id"], json.dumps(snapshot, allow_nan=False)))
            for head in ({kind, "previous"} if kind != "point" else {kind}):
                connection.execute("INSERT OR REPLACE INTO vd2_camera_return_heads VALUES (?,?)", (head, snapshot["id"]))
            return snapshot

    def get(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{32}", identity):
            raise ValueError("Invalid camera return point ID")
        with self.connection() as connection:
            row = connection.execute("SELECT value FROM vd2_camera_return_points WHERE id=?", (identity,)).fetchone()
        if not row:
            raise ValueError("Camera return point no longer exists")
        snapshot = json.loads(row[0])
        snapshot["settings"] = validate_settings(snapshot["settings"])
        return snapshot

    def options(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT kind,value FROM vd2_camera_return_heads JOIN vd2_camera_return_points USING(id)").fetchall()
        return {"previous": None, "alignment": None, "point": None, **{kind: json.loads(value) for kind, value in rows}}
