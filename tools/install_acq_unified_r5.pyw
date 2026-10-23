"""Cold unified r5 source installation; no launch, recovery or NI operations.

The exact existing ownership image, configuration, keys and journals are not
changed. Retired legacy launcher remains recoverable as an adjacent backup.
"""
import ast
import datetime
import hashlib
import json
import os
import shutil
import socket
import tkinter as tk
from tkinter import messagebox
import types
import uuid


TARGET = r"C:\ACQ_Python_Control_20261022_v8"
FILES = ("elyse_agent/acquisition_control_gui.py",
         "elyse_agent/acquisition_control_runtime.py",
         "elyse_agent/acquisition_recovery.py",
         "elyse_agent/handover_recovery.py",
         "elyse_agent/acquisition_startup.py",
         "elyse_agent/application_view.py",
         "elyse_agent/cooling_safety.py",
         "elyse_agent/journal_worker.py",
         "elyse_agent/dual_mode_telemetry.py")
MANIFEST = "manifest.json"
PLAN = "unified_r5_plan.json"
LEGACY_ENTRYPOINT = r"C:\ACQ_SharedState_Python34_20261014\shared_state_receiver.pyw"
LEGACY_SHA256 = "518119d596982efd9aa911430fd8f3473bdfcf04ae71e3f58b2d80a3fdc84aa0"
STARTUP_FILENAME = "ELYSE_Acquisition_Server.pyw"
STARTUP_MARKER = b"# ELYSE_ACQUISITION_COLD_LAUNCHER_V1"


def sha(path):
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def marker_image(target):
    path = os.path.join(target, "config.acquisition.control.json.ownership")
    try:
        with open(path, "rb") as stream:
            data = stream.read(4097)
    except OSError as error:
        if getattr(error, "errno", None) == 2:
            return None
        raise
    if len(data) > 4096:
        raise RuntimeError("Oversized ownership marker; source update refused")
    return data


def require_server_closed():
    connection = socket.socket()
    connection.settimeout(1)
    try:
        if connection.connect_ex(("127.0.0.1", 8772)) == 0:
            raise RuntimeError("Close unified server on 8772 first; no update performed")
    finally:
        connection.close()


def _valid_hash(value):
    return type(value) is str and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _installed_matches(path, digest):
    return not os.path.lexists(path) if digest is None else os.path.isfile(path) and sha(path) == digest


def _preflight(folder, target):
    with open(os.path.join(folder, PLAN), "r") as stream:
        plan = json.load(stream)
    if (type(plan) is not dict or set(plan) != {"files", "old_manifest_sha256", "new_manifest_sha256"}
            or type(plan["files"]) is not dict or set(plan["files"]) != set(FILES)
            or not _valid_hash(plan["old_manifest_sha256"])
            or not _valid_hash(plan["new_manifest_sha256"])):
        raise RuntimeError("Unexpected unified r5 source update scope")
    if sha(os.path.join(target, MANIFEST)) != plan["old_manifest_sha256"]:
        raise RuntimeError("Installed manifest differs; no update performed")
    for relative in FILES:
        expected = plan["files"][relative]
        if (type(expected) is not dict or set(expected) != {"old", "new"}
                or not _valid_hash(expected["new"])
                or expected["old"] is not None and not _valid_hash(expected["old"])):
            raise RuntimeError("Invalid source hash plan: " + relative)
        original = os.path.join(target, *relative.split("/"))
        incoming = os.path.join(folder, *relative.split("/"))
        if not _installed_matches(original, expected["old"]) or sha(incoming) != expected["new"]:
            raise RuntimeError("Source hash/absence mismatch: " + relative)
        with open(incoming, "rb") as stream:
            ast.parse(stream.read(), filename=relative)
    if sha(os.path.join(folder, MANIFEST)) != plan["new_manifest_sha256"]:
        raise RuntimeError("New manifest differs; no update performed")
    with open(os.path.join(folder, MANIFEST), "r") as stream:
        if type(json.load(stream)) is not dict:
            raise RuntimeError("New manifest must be a JSON object")
    return plan


def _retire_legacy_entrypoint():
    report = dict(status="absent", path=LEGACY_ENTRYPOINT)
    try:
        if not os.path.lexists(LEGACY_ENTRYPOINT):
            return report
        if not os.path.isfile(LEGACY_ENTRYPOINT) or sha(LEGACY_ENTRYPOINT) != LEGACY_SHA256:
            report.update(status="skipped_hash_mismatch",
                warning="Legacy entrypoint differs; retained unchanged")
            return report
        stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        backup = LEGACY_ENTRYPOINT + ".retired_" + stamp + "_" + uuid.uuid4().hex[:8] + ".bak"
        os.rename(LEGACY_ENTRYPOINT, backup)
        report.update(status="retired", backup=backup)
    except Exception as error:
        report.update(status="failed", warning="Legacy retirement failed: " + str(error))
    return report


def _load_startup_module(target):
    path = os.path.join(target, "elyse_agent", "acquisition_startup.py")
    # Compile the already hash-verified helper without writing __pycache__ or
    # importing any other installed application modules.
    module = types.ModuleType("_acq_r5_startup_" + uuid.uuid4().hex)
    module.__file__ = path
    exec(compile(_read_bytes(path), path, "exec"), module.__dict__)
    return module


def _migrate_existing_startup(target, folder=None):
    report = dict(status="absent")
    try:
        startup = _load_startup_module(target)
        if startup.FILENAME != STARTUP_FILENAME or startup.MARKER.encode("utf-8") != STARTUP_MARKER:
            raise RuntimeError("Unexpected unified Startup identity")
        folder = folder or startup.startup_directory()
        path = os.path.join(folder, STARTUP_FILENAME)
        report["path"] = path
        if not os.path.lexists(path):
            return report  # Never create autostart as an implicit source update.
        with open(path, "rb") as stream:
            original = stream.read(32769)
        if len(original) > 32768 or not original.startswith(STARTUP_MARKER):
            report.update(status="skipped_unmanaged", warning="Unmarked Startup file retained unchanged")
            return report
        prefix = STARTUP_FILENAME + ".backup_"
        before = set(name for name in os.listdir(folder) if name.startswith(prefix))
        migrated = startup.install_startup(os.path.join(target, "acquisition_control_server.pyw"),
            os.path.join(target, "config.acquisition.control.json"), folder=folder)
        after = set(name for name in os.listdir(folder) if name.startswith(prefix))
        backups = [os.path.join(folder, name) for name in sorted(after - before)]
        if not backups or not any(_read_bytes(path) == original for path in backups):
            raise RuntimeError("Startup migration did not retain an exact-byte original backup")
        report.update(status="migrated", path=migrated, backups=backups)
    except Exception as error:
        report.update(status="failed", warning="Existing Startup migration failed: " + str(error))
    return report


def _read_bytes(path):
    with open(path, "rb") as stream:
        return stream.read()


def install(folder, target=TARGET, retire_legacy=True, migrate_startup=True, startup_folder=None):
    require_server_closed()
    marker = marker_image(target)  # Read only: this is NOT NI ownership recovery.
    plan = _preflight(folder, target)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = os.path.join(target, "runtime", "source_before_unified_r5_" + stamp + "_" + uuid.uuid4().hex[:8])
    os.makedirs(backup)
    replacements = FILES + (MANIFEST,)
    for relative in replacements:
        if relative in FILES and plan["files"][relative]["old"] is None:
            continue
        original = os.path.join(target, *relative.split("/"))
        saved = os.path.join(backup, *relative.split("/"))
        os.makedirs(os.path.dirname(saved), exist_ok=True)
        shutil.copy2(original, saved)
    require_server_closed()
    if marker_image(target) != marker:
        raise RuntimeError("Ownership evidence changed during preflight; update refused")
    # Recheck every installed image after backup, before any source mutation.
    if sha(os.path.join(target, MANIFEST)) != plan["old_manifest_sha256"]:
        raise RuntimeError("Installed manifest changed during preflight; update refused")
    for relative in FILES:
        if not _installed_matches(os.path.join(target, *relative.split("/")), plan["files"][relative]["old"]):
            raise RuntimeError("Installed source changed during preflight: " + relative)
    for relative in replacements:
        incoming = os.path.join(folder, *relative.split("/"))
        original = os.path.join(target, *relative.split("/"))
        temporary = original + ".unified-r5-new"
        expected = plan["new_manifest_sha256"] if relative == MANIFEST else plan["files"][relative]["new"]
        with open(incoming, "rb") as source, open(temporary, "xb") as destination:
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        if sha(temporary) != expected:
            raise RuntimeError("Staged source changed; do not launch: " + relative)
        previous = plan["old_manifest_sha256"] if relative == MANIFEST else plan["files"][relative]["old"]
        if not _installed_matches(original, previous):
            raise RuntimeError("Installed source changed during update; do not launch: " + relative)
        os.replace(temporary, original)
        if sha(original) != expected:
            raise RuntimeError("Installed source mismatch; do not launch: " + relative)
    if marker_image(target) != marker:
        raise RuntimeError("Ownership evidence changed; do not launch")
    retirement = (_retire_legacy_entrypoint() if retire_legacy
                  else dict(status="not_requested", path=LEGACY_ENTRYPOINT))
    migration = (_migrate_existing_startup(target, folder=startup_folder) if migrate_startup
                 else dict(status="not_requested"))
    if marker_image(target) != marker:
        raise RuntimeError("Ownership evidence changed; do not launch")
    return dict(backup=backup, legacy_retirement=retirement, startup_migration=migration)


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        if not messagebox.askyesno("Install ONE unified Acquisition server r5",
                "Update nine verified source modules and manifest in the CLOSED unified server.\n"
                "Known originals will be backed up; prior ownership evidence remains unchanged.\n"
                "Retire only the exact verified old telemetry entrypoint to a recoverable backup.\n"
                "Migrate only an existing marked unified Startup launcher, preserving its exact bytes.\n\n"
                "NO server launch, acknowledgment, Initialize, NI calls or equipment commands.\n"
                "LabVIEW, configuration, keys and journals are not changed.\n\n"
                "Install unified r5?", parent=root):
            return
        report = install(os.path.dirname(os.path.abspath(__file__)))
        messagebox.showinfo("Unified r5 installed; not launched",
            json.dumps(report, indent=2) + "\n\nOpen the unified server separately; do NOT Initialize while VI runs.",
            parent=root)
    except Exception as error:
        messagebox.showerror("Source update refused; do not launch", str(error), parent=root)
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
