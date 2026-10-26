"""Install a verified portable Python runtime into a NEW local directory.

Python 3.4, stdlib only. Import is cold. No registry/PATH change, driver import,
NI library query, task creation, service start or process restart occurs here.
Only this invocation's new temporary directory may be removed on failure.
"""
import datetime
import hashlib
import io
import json
import os
import shutil
import stat
import uuid
import zipfile


TARGET = r"C:\Python34_ELYSE"
MANIFEST = "portable_runtime_manifest.json"
ROLE = "elyse_python34_x86_portable"
RESULT_ROLE = "elyse_python34_portable_install_result"
OWNER_MARKER = ".elyse_runtime_install_owner"
CORE_FILES = frozenset(("python.exe", "pythonw.exe", "python34.dll", "msvcr100.dll",
                        "Lib/os.py", "Lib/site.py", "DLLs/_tkinter.pyd"))


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                return value.hexdigest()
            value.update(block)


def safe_name(name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or name.startswith("/") or len(name) > 240):
        raise ValueError("Invalid portable-runtime relative path")
    parts = name.split("/")
    if any(not part or part in (".", "..") or part.endswith((".", " ")) for part in parts):
        raise ValueError("Unsafe portable-runtime path component")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {"COM" + str(n) for n in range(1, 10)} | {"LPT" + str(n) for n in range(1, 10)}
    if any(part.split(".")[0].upper() in reserved or any(ord(c) < 32 for c in part) for part in parts):
        raise ValueError("Windows device/control-character path refused")
    return parts


def safe_path(folder, name):
    parts = safe_name(name)
    folder = os.path.abspath(folder)
    path = os.path.abspath(os.path.join(folder, *parts))
    prefix = os.path.normcase(folder + os.sep)
    if not os.path.normcase(path).startswith(prefix):
        raise ValueError("Runtime path escapes its directory")
    candidate = folder
    for part in parts:
        candidate = os.path.join(candidate, part)
        if os.path.islink(candidate):
            raise ValueError("Runtime source/target cannot traverse symbolic links")
    return path


def manifest_identity(manifest):
    value = dict(role=manifest.get("role"), python=manifest.get("python"),
                 packages=manifest.get("packages"), files=manifest.get("files"))
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_manifest(folder):
    with io.open(os.path.join(folder, "runtime_manifest.json"), "r", encoding="utf-8") as stream:
        value = json.load(stream)
    if (type(value) is not dict or value.get("schema_version") != 1 or value.get("role") != ROLE
            or value.get("python") != dict(version="3.4.4", bits=32, implementation="CPython")
            or value.get("packages") != {"numpy": "1.15.4", "nidaqmx": "0.5.7", "six": "1.16.0"}
            or value.get("auto_initialize") is not False or value.get("changes_system_configuration") is not False):
        raise ValueError("Expected cold Python3.4.4 x86 runtime manifest")
    rows = value.get("files")
    if type(rows) is not list or not 1 <= len(rows) <= 10000:
        raise ValueError("Bounded complete file manifest required")
    seen, total = set(), 0
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "sha256", "bytes"}:
            raise ValueError("Exact runtime manifest file record required")
        safe_name(row["path"])
        name = row["path"].lower()
        if name in seen or row["path"] == MANIFEST:
            raise ValueError("Duplicate/reserved runtime path")
        seen.add(name)
        if (not isinstance(row["sha256"], str) or len(row["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in row["sha256"])
                or type(row["bytes"]) is not int or not 0 <= row["bytes"] <= 128 * 1024 * 1024):
            raise ValueError("Invalid file hash/size")
        total += row["bytes"]
    if total > 512 * 1024 * 1024 or not CORE_FILES <= set(row["path"] for row in rows):
        raise ValueError("Core runtime closure missing or oversized")
    if value.get("manifest_id") != manifest_identity(value):
        raise ValueError("Runtime manifest identity mismatch")
    return value


def verify_files(folder, manifest, installed=False):
    expected = set(row["path"] for row in manifest["files"])
    actual = set()
    for root, directories, files in os.walk(folder):
        if any(os.path.islink(os.path.join(root, name)) for name in directories):
            raise ValueError("Symbolic links are not part of the runtime")
        for name in files:
            relative = os.path.relpath(os.path.join(root, name), folder).replace(os.sep, "/")
            if installed and relative == MANIFEST:
                continue
            actual.add(relative)
    if actual != expected:
        raise ValueError("Runtime file closure differs from manifest")
    for row in manifest["files"]:
        path = safe_path(folder, row["path"])
        if os.path.getsize(path) != row["bytes"] or digest(path) != row["sha256"]:
            raise ValueError("Runtime file hash mismatch: " + row["path"])
    return True


def _remove_own_temporary(path, parent, token):
    """Never remove a pre-existing target, source package, or unrelated tree."""
    path, parent = os.path.abspath(path), os.path.abspath(parent)
    if (os.path.dirname(path) != parent or os.path.islink(path)
            or not os.path.basename(path).endswith(".installing-" + token)
            or os.path.normcase(os.path.realpath(os.path.dirname(path))) != os.path.normcase(os.path.realpath(parent))):
        raise RuntimeError("Refusing cleanup outside this installation's owned temporary directory")
    marker = os.path.join(path, OWNER_MARKER)
    with io.open(marker, "r", encoding="ascii") as stream:
        if stream.read() != token:
            raise RuntimeError("Temporary installation ownership marker changed")
    shutil.rmtree(path)


def _write_json(path, value):
    temporary = path + ".new-" + uuid.uuid4().hex
    try:
        with io.open(temporary, "x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.isfile(temporary):
            os.remove(temporary)


def install(folder, target=TARGET, copy_file=shutil.copy2, replace_directory=os.rename):
    folder, target = os.path.abspath(folder), os.path.abspath(target)
    manifest = load_manifest(folder)
    if os.path.islink(target) or not os.path.isdir(os.path.dirname(target)):
        raise ValueError("Existing plain local parent directory required")
    if os.path.exists(target):
        if not os.path.isdir(target) or not os.path.isfile(os.path.join(target, MANIFEST)):
            raise RuntimeError("Target already exists; unrelated runtime is never overwritten")
        with io.open(os.path.join(target, MANIFEST), "r", encoding="utf-8") as stream:
            installed = json.load(stream)
        if installed.get("manifest_id") != manifest["manifest_id"]:
            raise RuntimeError("Different existing portable runtime; no replacement performed")
        verify_files(target, manifest, installed=True)
        return dict(role=RESULT_ROLE, result="ALREADY_INSTALLED", target=target,
            manifest_id=manifest["manifest_id"], files=len(manifest["files"]),
            hardware_commands_sent=False, system_configuration_changed=False)

    archive = manifest.get("archive")
    source, bundle = os.path.join(folder, "runtime"), None
    if archive is not None:
        if type(archive) is not dict or set(archive) != {"path", "sha256"} or archive["path"] != "runtime.zip":
            raise ValueError("Expected runtime.zip package")
        archive_path = safe_path(folder, archive["path"])
        if digest(archive_path) != archive["sha256"]:
            raise ValueError("Runtime archive hash mismatch")
        bundle = zipfile.ZipFile(archive_path, "r")
        names = [row.filename for row in bundle.infolist()]
        expected = set(row["path"] for row in manifest["files"])
        sizes = dict((row["path"], row["bytes"]) for row in manifest["files"])
        if len(set(names)) != len(names) or set(names) != expected:
            bundle.close()
            raise ValueError("Archive file closure differs from manifest")
        for row in bundle.infolist():
            safe_name(row.filename)
            if stat.S_IFMT(row.external_attr >> 16) == stat.S_IFLNK or row.file_size != sizes[row.filename]:
                bundle.close()
                raise ValueError("Symbolic link or mismatched-size archive entries refused")
    else:
        verify_files(source, manifest)

    token = uuid.uuid4().hex
    parent = os.path.dirname(target)
    temporary = target + ".installing-" + token
    os.mkdir(temporary)
    with io.open(os.path.join(temporary, OWNER_MARKER), "x", encoding="ascii") as stream:
        stream.write(token)
    committed = False
    try:
        for row in manifest["files"]:
            destination = safe_path(temporary, row["path"])
            directory = os.path.dirname(destination)
            if not os.path.isdir(directory):
                os.makedirs(directory)
            if bundle is None:
                copy_file(safe_path(source, row["path"]), destination)
            else:
                with bundle.open(row["path"], "r") as incoming:
                    with open(destination, "xb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
            if os.path.getsize(destination) != row["bytes"] or digest(destination) != row["sha256"]:
                raise ValueError("Copied runtime hash mismatch: " + row["path"])
        _write_json(os.path.join(temporary, MANIFEST), manifest)
        os.remove(os.path.join(temporary, OWNER_MARKER))
        # Verify before the final rename. The target did not exist at entry;
        # Windows rename refuses a target created concurrently by another app.
        verify_files(temporary, manifest, installed=True)
        if os.path.exists(target):
            raise RuntimeError("Target appeared during copy; no replacement performed")
        replace_directory(temporary, target)
        committed = True
    except Exception:
        if os.path.isdir(temporary):
            # Recreate only our own marker after precommit verification removed
            # it. No successful final target is removed as a rollback action.
            marker = os.path.join(temporary, OWNER_MARKER)
            if not os.path.exists(marker):
                with io.open(marker, "x", encoding="ascii") as stream:
                    stream.write(token)
            _remove_own_temporary(temporary, parent, token)
        raise
    finally:
        if bundle is not None:
            bundle.close()
    if not committed:
        raise RuntimeError("Portable runtime installation did not commit")
    return dict(role=RESULT_ROLE, result="INSTALLED", target=target,
        manifest_id=manifest["manifest_id"], files=len(manifest["files"]),
        hardware_commands_sent=False, system_configuration_changed=False)


def install_and_record(folder, target=TARGET):
    result_path = os.path.join(os.path.abspath(folder), "python34_installation_result.json")
    try:
        result = install(folder, target)
    except Exception as error:
        result = dict(role=RESULT_ROLE, result="FAILED", target=os.path.abspath(target),
            error=type(error).__name__ + ": " + str(error), hardware_commands_sent=False,
            system_configuration_changed=False)
    result["recorded_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if os.path.exists(result_path):
        with io.open(result_path, "r", encoding="utf-8") as stream:
            if json.load(stream).get("role") != RESULT_ROLE:
                raise RuntimeError("Unrelated installation result file is not overwritten")
    _write_json(result_path, result)
    return result


def main():
    import tkinter as tk
    from tkinter import messagebox
    folder = os.path.dirname(os.path.abspath(__file__))
    root = tk.Tk()
    root.title("ELYSE portable Python 3.4 x86 installer")
    root.geometry("650x210")
    status = tk.StringVar(value="New directory only: " + TARGET + "\nNo NI calls, PATH or registry changes.")
    tk.Label(root, textvariable=status, justify="left", wraplength=620).pack(padx=12, pady=16)
    def run():
        if not messagebox.askyesno("Install portable Python", "Install the verified portable runtime into\n" + TARGET +
                "\n\nExisting unrelated directories are never replaced.\nNo NI hardware will be initialized.", parent=root):
            return
        button.configure(state="disabled")
        root.update_idletasks()
        try:
            result = install_and_record(folder)
            status.set(result["result"] + "\n" + result.get("error", "Runtime copied and verified. No program started."))
        except Exception as error:
            status.set(type(error).__name__ + ": " + str(error))
    button = tk.Button(root, text="Install portable Python", command=run)
    button.pack(pady=5)
    tk.Button(root, text="Close", command=root.destroy).pack(pady=5)
    root.mainloop()


if __name__ == "__main__":
    main()
