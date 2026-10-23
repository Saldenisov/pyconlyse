"""Cold five-file unified-server update; preserves prior NI ownership evidence.

No process termination, driver imports, recovery, NI calls or equipment commands.
The previous receive-only bridge may remain live during this source update.
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


TARGET = r"C:\ACQ_Python_Control_20261022_v8"
FILES = ("elyse_agent/acquisition_control_runtime.py", "elyse_agent/acquisition_backend.py",
         "elyse_agent/hardware_tasks.py", "elyse_agent/isolated_backend.py",
         "elyse_agent/isolated_worker.py")
MANIFEST = "manifest.json"


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


def install(folder, target=TARGET):
    require_server_closed()
    marker = marker_image(target)  # Read only; existing recovery is NOT cleared.
    with open(os.path.join(folder, "bootstrap_plan.json"), "r") as stream:
        plan = json.load(stream)
    if set(plan) != {"files", "old_manifest_sha256", "new_manifest_sha256"} or set(plan["files"]) != set(FILES):
        raise RuntimeError("Unexpected source update scope")
    if sha(os.path.join(target, MANIFEST)) != plan["old_manifest_sha256"]:
        raise RuntimeError("Installed manifest differs; no update performed")
    for relative in FILES:
        original = os.path.join(target, *relative.split("/"))
        incoming = os.path.join(folder, *relative.split("/"))
        expected = plan["files"][relative]
        if set(expected) != {"old", "new"} or sha(original) != expected["old"] or sha(incoming) != expected["new"]:
            raise RuntimeError("Source hash mismatch: " + relative)
        with open(incoming, "rb") as stream:
            ast.parse(stream.read(), filename=relative)
    if sha(os.path.join(folder, MANIFEST)) != plan["new_manifest_sha256"]:
        raise RuntimeError("New manifest differs; no update performed")
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = os.path.join(target, "runtime", "source_before_unified_bootstrap_" + stamp)
    os.makedirs(backup)
    replacements = FILES + (MANIFEST,)
    for relative in replacements:
        original = os.path.join(target, *relative.split("/"))
        saved = os.path.join(backup, *relative.split("/"))
        os.makedirs(os.path.dirname(saved), exist_ok=True)
        shutil.copy2(original, saved)
    require_server_closed()
    if marker_image(target) != marker:
        raise RuntimeError("Ownership evidence changed during preflight; update refused")
    for relative in replacements:
        incoming = os.path.join(folder, *relative.split("/"))
        original = os.path.join(target, *relative.split("/"))
        temporary = original + ".bootstrap-new"
        with open(incoming, "rb") as source, open(temporary, "xb") as destination:
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, original)
        if sha(original) != sha(incoming):
            raise RuntimeError("Installed source mismatch; do not launch: " + relative)
    if marker_image(target) != marker:
        raise RuntimeError("Ownership evidence changed; do not launch")
    return backup


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        if not messagebox.askyesno("Update ONE unified Acquisition server",
                "Update five source files and manifest in the CLOSED unified server.\n"
                "A verified source backup will be retained.\n"
                "LabVIEW and the existing telemetry bridge may continue running.\n\n"
                "NO Initialize, NI calls, equipment commands or process termination.\n"
                "Configuration, keys, journals and ownership marker stay unchanged.\n"
                "Prior recovery still blocks Initialize, NOT passive VI forwarding.\n\n"
                "Install the corrected unified server?", parent=root):
            return
        backup = install(os.path.dirname(os.path.abspath(__file__)))
        messagebox.showinfo("Unified source updated; no cards touched",
            "Verified backup:\n" + backup + "\n\n"
            "Stop and close ONLY the old Python telemetry bridge before opening\n"
            "the existing acquisition_control_server.pyw.\n"
            "Do NOT press Initialize while LabVIEW runs.\n"
            "RECOVERY_REQUIRED remains visible until separately verified recovery.", parent=root)
    except Exception as error:
        messagebox.showerror("Source update refused; do not launch", str(error), parent=root)
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
