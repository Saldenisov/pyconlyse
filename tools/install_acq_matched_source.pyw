"""Cold matched XP source update; no NI import, initialization or marker reset.

Run beside a verified package manifest. Preserves installed configuration and
ownership evidence, archives replaced files, and restores them on failure.
Python 3.4 compatible. Opening this utility never initializes equipment.
"""
import ast
import datetime
import hashlib
import json
import os
import shutil
import socket

TARGET = r"C:\ACQ_Python_Control_20261022_v8"
PRESERVE = ("config.acquisition.json", "config.acquisition.control.json")
CALIBRATION = ("data/calibration_map.csv", "data/ni6602_timing.csv")


def sha(path):
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def safe_path(root, name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError("Invalid package-relative path")
    root = os.path.abspath(root)
    path = os.path.abspath(os.path.join(root, *name.split("/")))
    if not path.lower().startswith((root + os.sep).lower()) or os.path.islink(path):
        raise ValueError("Source path escapes installation")
    return path


def require_closed():
    connection = socket.socket()
    connection.settimeout(1)
    try:
        if connection.connect_ex(("127.0.0.1", 8772)) == 0:
            raise RuntimeError("Close the old unified server on 8772 first")
    finally:
        connection.close()


def protected_image(target):
    result = {}
    for name in PRESERVE + ("config.acquisition.control.json.ownership",):
        path = safe_path(target, name)
        result[name] = sha(path) if os.path.exists(path) else None
    return result


def install(folder, target=TARGET, closed_check=require_closed, replace=os.replace):
    folder, target = os.path.abspath(folder), os.path.abspath(target)
    closed_check()
    before = protected_image(target)
    with open(os.path.join(folder, "manifest.json"), "r") as stream:
        manifest = json.load(stream)
    if (manifest.get("role") != "xp_python34" or manifest.get("named_operation_count") != 24
            or manifest.get("commands_default_enabled") is not False
            or manifest.get("auto_initialize") is not False):
        raise ValueError("Expected cold 24-operation XP package")
    names = [item["path"] for item in manifest["files"]]
    if len(names) != len(set(names)) or any(name.startswith("runtime/") for name in names):
        raise ValueError("Invalid source closure")
    for item in manifest["files"]:
        path = safe_path(folder, item["path"])
        if sha(path) != item["sha256"]:
            raise ValueError("Incoming package hash mismatch: " + item["path"])
        safe_path(target, item["path"])
        if path.endswith((".py", ".pyw")):
            with open(path, "rb") as stream:
                ast.parse(stream.read(), filename=item["path"])
    for name in CALIBRATION:
        if sha(safe_path(target, name)) != sha(safe_path(folder, name)):
            raise RuntimeError("Calibration differs; no source installed: " + name)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = os.path.join(target, "runtime", "source_before_matched_" + stamp)
    os.makedirs(backup)
    replacements = [name for name in names if name not in PRESERVE] + ["manifest.json"]
    existed = {}
    for name in replacements:
        original, saved = safe_path(target, name), safe_path(backup, name)
        existed[name] = os.path.isfile(original)
        if existed[name]:
            os.makedirs(os.path.dirname(saved), exist_ok=True)
            shutil.copy2(original, saved)
    # Copy-on-write manifest records the unchanged site configuration bytes.
    manifest = dict(manifest)
    for item in manifest["files"]:
        if item["path"] in PRESERVE:
            item["sha256"] = sha(safe_path(target, item["path"]))
    manifest["site_configuration_override"] = "Preserved installed configuration; no commissioning or key changes"
    changed, temporary_paths = [], []
    try:
        closed_check()
        if protected_image(target) != before:
            raise RuntimeError("Configuration/ownership evidence changed during preflight")
        for name in replacements:
            original = safe_path(target, name)
            temporary = original + ".matched-source-new"
            os.makedirs(os.path.dirname(original), exist_ok=True)
            with open(temporary, "xb") as destination:
                temporary_paths.append(temporary)
                if name == "manifest.json":
                    destination.write(json.dumps(manifest, indent=2).encode("utf-8"))
                else:
                    with open(safe_path(folder, name), "rb") as source:
                        shutil.copyfileobj(source, destination)
                destination.flush()
                os.fsync(destination.fileno())
            replace(temporary, original)
            changed.append(name)
        for item in manifest["files"]:
            if sha(safe_path(target, item["path"])) != item["sha256"]:
                raise RuntimeError("Installed hash mismatch: " + item["path"])
        if protected_image(target) != before:
            raise RuntimeError("Configuration/ownership evidence changed")
    except Exception:
        failures = []
        for name in reversed(changed):
            original = safe_path(target, name)
            try:
                if existed[name]:
                    shutil.copy2(safe_path(backup, name), original)
                else:
                    os.unlink(original)
            except Exception as error:
                failures.append(name + ": " + str(error))
        if failures:
            raise RuntimeError("Rollback incomplete; do not launch: " + "; ".join(failures))
        raise
    finally:
        for temporary in temporary_paths:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return dict(result="INSTALLED", backup=backup, files=len(manifest["files"]),
                configuration_preserved=True, ownership_preserved=True,
                cards_initialized=False, hardware_commands_sent=False)


def main():
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    folder = os.path.dirname(os.path.abspath(__file__))
    try:
        result = install(folder)
        with open(os.path.join(folder, "installation_result.json"), "w") as stream:
            json.dump(result, stream, indent=2)
        messagebox.showinfo("Matched source installed", "Source verified. Configuration and ownership evidence preserved.\n"
            "No cards initialized.\nBackup: " + result["backup"] + "\n\nOpen acquisition_control_server.pyw in the original installation.", parent=root)
    except Exception as error:
        with open(os.path.join(folder, "installation_result.json"), "w") as stream:
            json.dump(dict(result="FAILED", error=str(error)), stream, indent=2)
        messagebox.showerror("Matched update refused; no Initialize", str(error), parent=root)
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
