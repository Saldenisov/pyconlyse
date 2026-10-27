"""Cold r18 source installation into a NEW role directory; Python 3.4 stdlib.

No process discovery/start/stop, NI imports, network access, registry, PATH or
security changes. Package and site manifests require independently supplied
SHA256 pins. A different/changed existing target is never overwritten.
"""
import argparse
import datetime
import hashlib
import io
import json
import math
import os
import shutil
import uuid


RELEASE = "elyse-card-process-orchestrators-20261026-r18"
TARGETS = dict(acquisition=r"C:\ELYSE_Orchestrator_Acquisition_r18",
               supervision=r"C:\ELYSE_Orchestrator_Supervision_r18")
RUNTIME = r"C:\Python34_ELYSE"
SOURCE_MANIFEST = "source_manifest.json"
INSTALL_MANIFEST = "orchestrator_installation.json"
OWNER_MARKER = ".elyse_source_install_owner"
DEFAULT_CONFIGS = frozenset(("config.acquisition.json", "config.acquisition.control.json", "config.supervision.control.json"))
ENTRYPOINTS = dict(acquisition="acquisition_control_server.pyw", supervision="supervision_control_server.pyw")
CONFIGS = dict(acquisition="config.acquisition.control.json", supervision="config.supervision.control.json")
RESULT_KIND = "ELYSE_COLD_SOURCE_INSTALLATION_RESULT"


def digest(path):
    result = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                return result.hexdigest()
            result.update(block)


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _finite(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _name(name):
    if (type(name) is not str or not name or len(name) > 220 or "\\" in name or ":" in name
            or name.startswith("/")):
        raise ValueError("Plain bounded relative file name required")
    parts = name.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {"COM" + str(i) for i in range(1, 10)} | {"LPT" + str(i) for i in range(1, 10)}
    if any(not p or p in (".", "..") or p.endswith((".", " "))
           or p.split(".")[0].upper() in reserved or any(ord(c) < 32 for c in p) for p in parts):
        raise ValueError("Unsafe Windows path refused")
    return parts


def _plain(path):
    if not os.path.lexists(path):
        return
    if os.path.islink(path) or getattr(os.lstat(path), "st_file_attributes", 0) & 1024:
        raise ValueError("Symbolic links/reparse points refused")
    if os.name == "nt":
        # Python3.4 does not expose st_file_attributes on every Windows build.
        import ctypes
        getter = ctypes.windll.kernel32.GetFileAttributesW
        getter.argtypes, getter.restype = [ctypes.c_wchar_p], ctypes.c_uint32
        attributes = getter(os.path.abspath(path))
        if attributes == 0xffffffff or attributes & 1024:
            raise ValueError("Unreadable/reparse-point installation path refused")


def safe_path(folder, name):
    parts = _name(name)
    folder = os.path.abspath(folder)
    ancestor = folder
    while True:
        _plain(ancestor)
        parent = os.path.dirname(ancestor)
        if parent == ancestor:
            break
        ancestor = parent
    current = folder
    for part in parts:
        current = os.path.join(current, part)
        _plain(current)
    if not os.path.normcase(os.path.abspath(current)).startswith(os.path.normcase(folder + os.sep)):
        raise ValueError("Path escapes installation root")
    return current


def _read_json(path, maximum=1024 * 1024):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field refused")
            result[key] = value
        return result
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Nonfinite JSON number refused")
        return number
    def reject_constant(value):
        raise ValueError("Nonstandard JSON number refused: " + value)
    with open(path, "rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Bounded JSON document required")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_float=finite_float, parse_constant=reject_constant)


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def _rows(value):
    rows = value.get("files")
    if type(rows) is not list or not 1 <= len(rows) <= 1024:
        raise ValueError("Bounded explicit manifest closure required")
    seen = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "sha256"} or not _hash(row["sha256"]):
            raise ValueError("Exact path/SHA256 manifest record required")
        _name(row["path"])
        folded = row["path"].lower()
        if folded in seen:
            raise ValueError("Duplicate case-insensitive manifest path refused")
        seen.add(folded)
    return rows


def _closure(folder, ignored=()):
    _plain(folder)
    result = set()
    for root, directories, files in os.walk(folder):
        for name in directories + files:
            _plain(os.path.join(root, name))
        for name in files:
            relative = os.path.relpath(os.path.join(root, name), folder).replace(os.sep, "/")
            if relative not in ignored:
                _name(relative)
                result.add(relative)
    return result


def _verify(folder, rows, ignored=()):
    if _closure(folder, ignored) != set(row["path"] for row in rows):
        raise ValueError("Directory closure differs from pinned manifest")
    total = 0
    for row in rows:
        path = safe_path(folder, row["path"])
        size = os.path.getsize(path)
        total += size
        if size > 16 * 1024 * 1024 or total > 64 * 1024 * 1024 or digest(path) != row["sha256"]:
            raise ValueError("Bounded file hash verification failed: " + row["path"])


def _pinned_manifest(folder, name, pin):
    if not _hash(pin):
        raise ValueError("External lower-case manifest SHA256 pin required")
    path = safe_path(folder, name)
    if digest(path) != pin:
        raise ValueError("Pinned manifest mismatch: " + name)
    value = _read_json(path)
    if type(value) is not dict:
        raise ValueError("Manifest object required")
    return value


def _source(folder, pin):
    manifest = _pinned_manifest(folder, "manifest.json", pin)
    if (manifest.get("schema_version") != 1 or manifest.get("role") != "xp_python34"
            or manifest.get("release") != RELEASE or manifest.get("named_operation_count") != 25
            or manifest.get("standard_bank_count") != 27 or manifest.get("auto_initialize") is not False
            or manifest.get("hardware_activated") is not False or manifest.get("commands_default_enabled") is not False
            or manifest.get("federation_default_enabled") is not False):
        raise ValueError("Expected cold two-orchestrator r17 source package")
    rows = _rows(manifest)
    names = set(row["path"] for row in rows)
    if not set(ENTRYPOINTS.values()) | DEFAULT_CONFIGS <= names:
        raise ValueError("Both cold entrypoints and package configuration defaults required")
    reserved = {name.lower() for name in (SOURCE_MANIFEST, INSTALL_MANIFEST, OWNER_MARKER, "START.cmd", "site_manifest.json")}
    if any(name.lower() in reserved or name.lower().startswith("package_defaults/") for name in names):
        raise ValueError("Source path collides with installation metadata")
    _verify(folder, rows, ignored=("manifest.json",))
    return manifest, rows


def _key(folder, name, names):
    _name(name)
    if name not in names or name.lower().endswith((".py", ".pyw", ".dll", ".pyd", ".exe", ".cmd", ".lnk")):
        raise ValueError("Manifest-listed installation-local key file required")
    with open(safe_path(folder, name), "rb") as stream:
        value = stream.read(4097).strip()
    if not 32 <= len(value) <= 4096:
        raise ValueError("Bounded key of at least 32 bytes required")
    return value


def _site(folder, pin, role):
    manifest = _pinned_manifest(folder, "site_manifest.json", pin)
    if (set(manifest) != {"schema_version", "role", "release", "files"}
            or manifest["schema_version"] != 1 or manifest["role"] != role or manifest["release"] != RELEASE):
        raise ValueError("Exact role-specific r17 site manifest required")
    rows = _rows(manifest)
    result_name = "installation_result." + role + ".json"
    result_path = safe_path(folder, result_name)
    if os.path.exists(result_path):
        existing = _read_json(result_path, 8192)
        if type(existing) is not dict or existing.get("kind") != RESULT_KIND or existing.get("role") != role:
            raise ValueError("Unrelated installation result is preserved")
    _verify(folder, rows, ignored=("site_manifest.json", result_name))
    names = set(row["path"] for row in rows)
    config = _read_json(safe_path(folder, CONFIGS[role]), 16384)
    if type(config) is not dict:
        raise ValueError("Role configuration object required")
    if role == "acquisition":
        base = _read_json(safe_path(folder, "config.acquisition.json"), 16384)
        required = {"bind_host", "port", "key_file", "period_seconds", "read_timeout_seconds"}
        allowed = required | {"native_isolation_mode", "control_profile", "focal_stop", "ht_shutdown",
            "stage_controls_verified", "cooling_trip_verified", "ht_controls_verified", "focal_controls_verified",
            "counter_controls_verified", "ht_voltage_controls_verified", "outer_stop_verified",
            "counter_timing_controls_verified", "beamline_controls_verified", "operator_supervised_test"}
        if (type(base) is not dict or not required <= set(base) or set(base) - allowed
                or base["bind_host"] != "10.20.30.10" or type(base["port"]) is not int or base["port"] != 8772
                or base.get("native_isolation_mode") != "per_card"
                or base.get("control_profile", "legacy_full") not in ("legacy_full", "general_only_test", "extended_ht_stop")
                or not _finite(base["period_seconds"], .02, 10) or not _finite(base["read_timeout_seconds"], .01, 2)
                or any(type(base[name]) is not bool for name in base if name.endswith("_verified") or name == "operator_supervised_test")):
            raise ValueError("Fixed Acquisition per-card local configuration required")
        focal, ht = base.get("focal_stop", {}), base.get("ht_shutdown", {})
        if (type(focal) is not dict or set(focal) - {"dll_path", "resources_verified", "timeout_seconds"}
                or type(focal.get("resources_verified", False)) is not bool
                or not _finite(focal.get("timeout_seconds", 10), 1, 30)
                or "dll_path" in focal and (type(focal["dll_path"]) is not str or not focal["dll_path"])):
            raise ValueError("Existing explicit Focales policy required")
        if (type(ht) is not dict or set(ht) - {"feedback_verified", "zero_tolerance_kv", "timeout_seconds"}
                or type(ht.get("feedback_verified", False)) is not bool
                or not _finite(ht.get("zero_tolerance_kv", 0), 0, 8)
                or ht.get("zero_tolerance_kv", 0) == 8
                or not _finite(ht.get("timeout_seconds", 10), 0, 120)
                or ht.get("timeout_seconds", 10) == 0):
            raise ValueError("Existing explicit HT shutdown policy required")
        if (set(config) != {"remote_control_enabled", "command_key_file", "cooling_safety", "telemetry"}
                or type(config["remote_control_enabled"]) is not bool):
            raise ValueError("Exact separate Acquisition control configuration required")
        cooling = config["cooling_safety"]
        if (type(cooling) is not dict or set(cooling) != {"polarity_verified", "journal_file"}
                or type(cooling["polarity_verified"]) is not bool):
            raise ValueError("Existing explicit cooling policy required")
        _name(cooling["journal_file"])
        if cooling["journal_file"] in names:
            raise ValueError("Runtime journal cannot overwrite a staged source/configuration/key")
        telemetry = config["telemetry"]
        if (type(telemetry) is not dict or set(telemetry) != {"enabled", "host", "port", "period_seconds", "wire_mode"}
                or telemetry["enabled"] is not True
                or telemetry["wire_mode"] not in ("legacy_27", "federated_owner")):
            raise ValueError("Explicit enabled Acquisition telemetry wire mode required")
        keys = (base["key_file"], config["command_key_file"])
        expected = {"config.acquisition.json", CONFIGS[role]} | set(keys)
    else:
        required = {"schema_version", "bind_host", "port", "read_key_file", "command_key_file",
                "remote_control_enabled", "counter_timing_controls_verified", "period_seconds", "read_timeout_seconds", "video", "telemetry"}
        if (not required <= set(config) or set(config) - required - {"vi_passive_shadow"}
                or type(config.get("vi_passive_shadow", False)) is not bool
                or config["schema_version"] != 1 or config["bind_host"] != "10.20.30.2"
                or type(config["port"]) is not int or config["port"] != 8772
                or config["remote_control_enabled"] is not False or config["counter_timing_controls_verified"] is not False
                or not _finite(config["period_seconds"], .02, 10) or not _finite(config["read_timeout_seconds"], .01, 2)
                or config["video"] != dict(channel=2, white_ref_volt=.9, black_ref_volt=.1)):
            raise ValueError("Cold uncommissioned fixed SuperVision source configuration required")
        telemetry = config["telemetry"]
        if (type(telemetry) is not dict or set(telemetry) != {"enabled", "wire", "host", "port", "period_seconds"}
                or type(telemetry["enabled"]) is not bool or telemetry["wire"] != "federated_owner"):
            raise ValueError("Explicit SuperVision telemetry enablement and owner wire required")
        keys = (config["read_key_file"], config["command_key_file"])
        if any(len(_name(name)) != 1 for name in keys):
            raise ValueError("SuperVision keys use installation-local basenames")
        expected = {CONFIGS[role]} | set(keys)
    if (telemetry.get("host") != "10.20.30.202" or type(telemetry.get("port")) is not int or telemetry["port"] != 8767
            or not _finite(telemetry.get("period_seconds"), .05, 10)):
        raise ValueError("Fixed Everest destination required")
    if "START.lnk" in names:
        expected.add("START.lnk")  # Reviewed/pinned by staging; never launched here.
    if names != expected or len(set(name.lower() for name in keys)) != 2:
        raise ValueError("Site closure must contain exactly role configurations and two separate keys")
    if _key(folder, keys[0], names) == _key(folder, keys[1], names):
        raise ValueError("Read and command key contents must be distinct")
    return manifest, rows


def _runtime(folder):
    path = safe_path(folder, "portable_runtime_manifest.json")
    manifest = _read_json(path, 4 * 1024 * 1024)
    if (manifest.get("role") != "elyse_python34_x86_portable"
            or manifest.get("python") != dict(version="3.4.4", bits=32, implementation="CPython")):
        raise ValueError("Separately installed portable CPython3.4.4 x86 required")
    identity = {key: manifest.get(key) for key in ("role", "python", "packages", "files")}
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != manifest.get("manifest_id"):
        raise ValueError("Portable runtime identity mismatch")
    matches = [row for row in manifest.get("files", []) if row.get("path") == "pythonw.exe"]
    if len(matches) != 1 or digest(safe_path(folder, "pythonw.exe")) != matches[0]["sha256"]:
        raise ValueError("Portable pythonw.exe hash mismatch")
    return manifest["manifest_id"]


def _remove_owned(path, parent, token):
    path, parent = os.path.abspath(path), os.path.abspath(parent)
    if (os.path.dirname(path) != parent or not os.path.basename(path).endswith(".installing-" + token)
            or os.path.normcase(os.path.realpath(os.path.dirname(path))) != os.path.normcase(os.path.realpath(parent))):
        raise RuntimeError("Temporary cleanup outside owned sibling refused")
    _plain(path)
    with io.open(os.path.join(path, OWNER_MARKER), "r", encoding="ascii") as stream:
        if stream.read() != token:
            raise RuntimeError("Temporary ownership changed; no cleanup performed")
    # Refuse deletion if a replaced copy callback or concurrent editor inserted
    # a reparse point. Python3.4/XP rmtree cannot certify junction containment.
    for root, directories, files in os.walk(path):
        for name in directories + files:
            _plain(os.path.join(root, name))
    shutil.rmtree(path)


def install(package, site, role, source_pin, site_pin, target=None, runtime=RUNTIME,
            copy_file=shutil.copy2, rename_directory=os.rename):
    """Target/runtime overrides are local RAM-fixture seams, never network fields."""
    if role not in TARGETS:
        raise ValueError("Exact acquisition/supervision role required")
    package, site, runtime = [os.path.abspath(path) for path in (package, site, runtime)]
    target = os.path.abspath(TARGETS[role] if target is None else target)
    parent = os.path.dirname(target)
    _plain(parent)
    _plain(target)
    if not os.path.isdir(parent) or target in (package, site, runtime):
        raise ValueError("New distinct target under existing plain local parent required")
    source, source_rows = _source(package, source_pin)
    site_manifest, site_rows = _site(site, site_pin, role)
    runtime_id = _runtime(runtime)
    transfers = []
    for row in source_rows:
        name = "package_defaults/" + row["path"] if row["path"] in DEFAULT_CONFIGS else row["path"]
        transfers.append((safe_path(package, row["path"]), name, row["sha256"]))
    for row in site_rows:
        transfers.append((safe_path(site, row["path"]), row["path"], row["sha256"]))
    names = [row[1].lower() for row in transfers]
    if len(names) != len(set(names)):
        raise ValueError("Site file collides with source closure")
    launcher = ('@echo off\r\ncd /d "{0}"\r\n"{1}" -B "{0}\\{2}" --config "{0}\\{3}"\r\n'.format(
        target, os.path.join(runtime, "pythonw.exe"), ENTRYPOINTS[role], CONFIGS[role])).encode("utf-8")
    with open(safe_path(package, "manifest.json"), "rb") as stream:
        source_raw = stream.read()
    with open(safe_path(site, "site_manifest.json"), "rb") as stream:
        site_raw = stream.read()
    if hashlib.sha256(source_raw).hexdigest() != source_pin or hashlib.sha256(site_raw).hexdigest() != site_pin:
        raise ValueError("Pinned manifest changed during preflight")
    generated = {SOURCE_MANIFEST: source_raw, "site_manifest.json": site_raw, "START.cmd": launcher}
    final_rows = [dict(path=name, sha256=sha) for path, name, sha in transfers]
    final_rows += [dict(path=name, sha256=hashlib.sha256(raw).hexdigest()) for name, raw in generated.items()]
    final_rows.sort(key=lambda row: row["path"])
    receipt = dict(schema_version=1, kind="ELYSE_COLD_ORCHESTRATOR_INSTALLATION", role=role, release=RELEASE,
        source_manifest_sha256=source_pin, site_manifest_sha256=site_pin,
        portable_runtime_id=runtime_id, runtime=runtime, target=target, files=final_rows,
        host_ip_verified=False, auto_initialize=False, hardware_commands_sent=False,
        processes_started=False, system_configuration_changed=False)
    receipt_raw = _json_bytes(receipt)
    if os.path.lexists(target):
        if not os.path.isdir(target):
            raise RuntimeError("Existing unrelated target is never overwritten")
        stored = safe_path(target, INSTALL_MANIFEST)
        if not os.path.isfile(stored) or _read_json(stored) != receipt:
            raise RuntimeError("Different existing installation; no replacement performed")
        _verify(target, final_rows, ignored=(INSTALL_MANIFEST,))
        return dict(result="ALREADY_INSTALLED", role=role, target=target, hardware_commands_sent=False)
    token = uuid.uuid4().hex
    temporary = target + ".installing-" + token
    os.mkdir(temporary)
    marker = os.path.join(temporary, OWNER_MARKER)
    with io.open(marker, "x", encoding="ascii") as stream:
        stream.write(token)
    try:
        for source_path, name, sha in transfers:
            destination = safe_path(temporary, name)
            if not os.path.isdir(os.path.dirname(destination)):
                os.makedirs(os.path.dirname(destination))
            copy_file(source_path, destination)
            if digest(destination) != sha:
                raise ValueError("Copied source/site hash mismatch: " + name)
        for name, raw in dict(generated, **{INSTALL_MANIFEST: receipt_raw}).items():
            with open(safe_path(temporary, name), "xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        _verify(temporary, final_rows, ignored=(INSTALL_MANIFEST, OWNER_MARKER))
        os.remove(marker)
        if os.path.lexists(target):
            raise RuntimeError("Target appeared during copy; no replacement performed")
        rename_directory(temporary, target)
    except Exception:
        if os.path.isdir(temporary):
            if not os.path.exists(marker):
                with io.open(marker, "x", encoding="ascii") as stream:
                    stream.write(token)
            _remove_owned(temporary, parent, token)
        raise
    return dict(result="INSTALLED", role=role, target=target, hardware_commands_sent=False,
                processes_started=False, system_configuration_changed=False)


def _record_result(site, role, result):
    """A separate bounded result, never keys or copied configuration bytes."""
    path = safe_path(os.path.abspath(site), "installation_result." + role + ".json")
    if os.path.exists(path):
        old = _read_json(path, 8192)
        if type(old) is not dict or old.get("kind") != RESULT_KIND or old.get("role") != role:
            raise RuntimeError("Unrelated result file is not overwritten")
    value = dict(result, kind=RESULT_KIND, role=role,
        recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    raw = _json_bytes(value)
    if len(raw) > 8192:
        raise ValueError("Bounded installation result required")
    temporary = path + ".new-" + uuid.uuid4().hex
    try:
        with open(temporary, "xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.isfile(temporary):
            os.remove(temporary)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--role", required=True, choices=sorted(TARGETS))
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--site-manifest-sha256", required=True)
    parser.add_argument("--gui", action="store_true", help="Show result/error and record a separate site result; never launch server")
    options = parser.parse_args(argv)
    if options.gui:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            try:
                result = install(options.package, options.site, options.role,
                                 options.manifest_sha256, options.site_manifest_sha256)
            except Exception as error:
                result = dict(result="FAILED", error=type(error).__name__ + ": " + str(error)[:600],
                    target=TARGETS[options.role], hardware_commands_sent=False,
                    processes_started=False, system_configuration_changed=False)
            try:
                result_path = _record_result(options.site, options.role, result)
            except Exception as error:
                messagebox.showerror("ELYSE source installation result could not be recorded",
                    json.dumps(result, sort_keys=True, indent=2) + "\n\nResult record: " + str(error), parent=root)
                return 1
            text = json.dumps(result, sort_keys=True, indent=2) + "\n\nResult: " + result_path
            if result["result"] == "FAILED":
                messagebox.showerror("ELYSE source installation failed", text, parent=root)
                return 1
            messagebox.showinfo("ELYSE source installed; server remains stopped", text, parent=root)
            return 0
        finally:
            root.destroy()
    result = install(options.package, options.site, options.role,
                     options.manifest_sha256, options.site_manifest_sha256)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
