"""Build a cold, portable Python3.4.4 x86 runtime from reviewed LOCAL files.

No network download, pip, registry/PATH mutation, XP access or hardware call.
The only process launched is a new private cold-import probe. A timeout may
terminate ONLY that owned probe. Existing Python installations are untouched.
"""
import argparse
import datetime
import hashlib
import importlib.machinery
import io
import json
import os
import shutil
import struct
import subprocess
import tempfile
import uuid
import zipfile


BASE = r"C:\dev\pyconlyse\tools\xp_python34_extracted"
PACKAGES = r"C:\dev\pyconlyse\tools\xp_python34_testenv\Lib\site-packages"
VC_RUNTIME = r"C:\Windows\SysWOW64\msvcr100.dll"
PINS = {"numpy": "1.15.4", "nidaqmx": "0.5.7", "six": "1.16.0"}
SKIP_DIRECTORIES = frozenset(("__pycache__", "tests", "test", ".git", ".svn", "demos", "idle_test"))
NATIVE_EXTENSIONS = frozenset((".exe", ".dll", ".pyd"))


PROBE = r'''"""Cold import verification only; no Task construction or NI library access."""
import ctypes
import email.parser
import json
import os
import platform
import struct
import sys

root = os.path.dirname(os.path.abspath(__file__))
if tuple(sys.version_info[:3]) != (3, 4, 4) or struct.calcsize("P") != 4:
    raise RuntimeError("Expected actual CPython3.4.4 x86")
if os.path.normcase(os.path.abspath(sys.prefix)) != os.path.normcase(root):
    raise RuntimeError("Portable interpreter resolved an external Python prefix")

ni_library_attempts = []
def guarded_loader(original):
    def load(name, *arguments, **keywords):
        text = str(name).lower()
        if any(part in text for part in ("nicaiu", "nidaq", "imaq")):
            ni_library_attempts.append(str(name))
            raise AssertionError("Cold probe attempted an NI library load")
        return original(name, *arguments, **keywords)
    return load
ctypes.CDLL = guarded_loader(ctypes.CDLL)
ctypes.cdll._dlltype = guarded_loader(ctypes.cdll._dlltype)
if hasattr(ctypes, "WinDLL"):
    ctypes.WinDLL = guarded_loader(ctypes.WinDLL)
    ctypes.windll._dlltype = guarded_loader(ctypes.windll._dlltype)

task_attempts = []
def no_task_profile(frame, event, arg):
    filename = frame.f_code.co_filename.replace("\\", "/").lower()
    if event == "call" and filename.endswith("/nidaqmx/task.py") and frame.f_code.co_name == "__init__":
        task_attempts.append("Task.__init__")
        raise AssertionError("Cold probe attempted NI Task construction")
sys.setprofile(no_task_profile)
try:
    import ssl, sqlite3, ctypes, multiprocessing, queue, threading, socket
    import tkinter
    tcl = tkinter.Tcl()
    tcl_patch = tcl.eval("info patchlevel")
    import numpy
    import six
    import nidaqmx
    from nidaqmx._lib import lib_importer
finally:
    sys.setprofile(None)

prefix = os.path.normcase(root + os.sep)
for module in (numpy, six, nidaqmx):
    if not os.path.normcase(os.path.abspath(module.__file__)).startswith(prefix):
        raise RuntimeError("Required package resolved outside the portable runtime")
state = vars(lib_importer)
if any(state.get(name) is not None for name in ("_windll", "_cdll", "_task_handle", "_cal_handle")):
    raise AssertionError("NI library/handle state was initialized by a cold import")
with open(os.path.join(root, "Lib", "site-packages", "nidaqmx-0.5.7.dist-info", "METADATA"), "r") as stream:
    ni_version = email.parser.Parser().parsestr(stream.read())["Version"]
if (numpy.__version__, ni_version, six.__version__) != ("1.15.4", "0.5.7", "1.16.0"):
    raise RuntimeError("Required package version mismatch")
print(json.dumps(dict(ok=True, python=platform.python_version(), bits=struct.calcsize("P") * 8,
    numpy=numpy.__version__, nidaqmx=ni_version, six=six.__version__, tcl=tcl_patch,
    tk=tkinter.TkVersion, task_constructed=False, ni_library_queried=False,
    driver_state_cold=True, registry_changed=False, path_changed=False)))
'''


def _installer():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "install_xp_python34_runtime.pyw")
    return importlib.machinery.SourceFileLoader("_elyse_portable_runtime_installer", path).load_module()


def _text(path, value):
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with io.open(path, "w", encoding="utf-8") as stream:
        stream.write(value)


def pe_machine(path):
    """Read PE headers only; never load a DLL or query a native driver."""
    with open(path, "rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Expected a Windows PE executable: " + path)
        stream.seek(0x3c)
        raw = stream.read(4)
        if len(raw) != 4:
            raise ValueError("Truncated PE header")
        stream.seek(struct.unpack("<I", raw)[0])
        if stream.read(4) != b"PE\0\0":
            raise ValueError("Invalid PE signature")
        raw = stream.read(2)
        if len(raw) != 2:
            raise ValueError("Truncated PE machine")
        return struct.unpack("<H", raw)[0]


def selected_tree(folder, target_prefix, skip_roots=()):
    """Reviewable file selection, excluding caches/tests and arbitrary extras."""
    result = []
    for root, directories, files in os.walk(folder):
        relative = os.path.relpath(root, folder)
        parts = () if relative == "." else tuple(relative.split(os.sep))
        directories[:] = sorted(name for name in directories
            if name not in SKIP_DIRECTORIES and not (not parts and name in skip_roots))
        for name in sorted(files):
            source = os.path.join(root, name)
            if os.path.islink(source) or any(os.path.islink(os.path.join(root, name)) for name in directories):
                raise ValueError("Runtime source trees cannot contain symbolic links")
            if name.lower().endswith((".pyc", ".pyo", ".msi", ".whl", ".chm", ".pdb", ".exe",
                                      ".key", ".pem", ".pfx", ".p12")) or name == ".env":
                continue
            target = "/".join((target_prefix,) + parts + (name,))
            result.append((source, target))
    return result


def _metadata_version(path):
    import email.parser
    with io.open(path, "r", encoding="utf-8") as stream:
        metadata = email.parser.Parser().parsestr(stream.read())
    return metadata.get("Name", "").lower(), metadata.get("Version")


def runtime_sources(base, packages, vc_runtime):
    selected = []
    for name in ("python.exe", "pythonw.exe", "python34.dll", "LICENSE.txt"):
        source = os.path.join(base, name)
        if not os.path.isfile(source):
            raise ValueError("Required local Python file missing: " + source)
        selected.append((source, name))
    selected.extend(selected_tree(os.path.join(base, "Lib"), "Lib",
                                  skip_roots=("site-packages", "ensurepip", "turtledemo")))
    selected.extend((source, target) for source, target in selected_tree(os.path.join(base, "DLLs"), "DLLs")
                    if not os.path.basename(source).startswith(("_test", "_ctypes_test"))
                    and not source.lower().endswith(".ico"))
    for name in ("tcl8", "tcl8.6", "tk8.6"):
        source = os.path.join(base, "tcl", name)
        if not os.path.isdir(source):
            raise ValueError("Required local Tcl/Tk scripts missing: " + source)
        selected.extend(selected_tree(source, "tcl/" + name))
    if not os.path.isfile(vc_runtime):
        raise ValueError("Reviewed x86 msvcr100.dll must be supplied locally")
    selected.append((vc_runtime, "msvcr100.dll"))
    for name, version in sorted(PINS.items()):
        info = name + "-" + version + ".dist-info"
        if _metadata_version(os.path.join(packages, info, "METADATA")) != (name, version):
            raise ValueError("Installed local package pin mismatch: " + name)
        if name == "six":
            selected.append((os.path.join(packages, "six.py"), "Lib/site-packages/six.py"))
        else:
            selected.extend(selected_tree(os.path.join(packages, name), "Lib/site-packages/" + name))
        # Keep the original wheel metadata and available license notices.
        # RECORD is omitted because tests/caches are deliberately not copied.
        for filename in ("METADATA", "WHEEL", "LICENSE", "LICENSE.txt", "COPYING", "DESCRIPTION.rst"):
            source = os.path.join(packages, info, filename)
            if os.path.isfile(source):
                selected.append((source, "Lib/site-packages/" + info + "/" + filename))
    names = [target.lower() for source, target in selected]
    if len(set(names)) != len(names):
        raise ValueError("Portable runtime selection contains a Windows path collision")
    return selected


def probe_runtime(runtime, timeout=30., popen=subprocess.Popen):
    """Run exactly one owned, bounded probe; never touch existing processes."""
    environment = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "TCL_LIBRARY", "TK_LIBRARY", "VIRTUAL_ENV"):
        environment.pop(name, None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    options = dict(cwd=runtime, env=environment, stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        options.update(startupinfo=startup, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    process = popen([os.path.join(runtime, "python.exe"), "-E", "-s", "-B",
                     os.path.join(runtime, "verify_portable_runtime.py")], **options)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()  # ONLY the private probe Popen object created above.
        stdout, stderr = process.communicate()
        raise RuntimeError("Owned cold-import probe timed out; only probe PID {0} terminated".format(process.pid))
    if process.returncode != 0:
        raise RuntimeError("Portable cold-import probe failed: " + stderr.decode("utf-8", "replace")[-6000:])
    result = json.loads(stdout.decode("utf-8").strip().splitlines()[-1])
    if (result.get("ok") is not True or result.get("python") != "3.4.4" or result.get("bits") != 32
            or result.get("task_constructed") is not False or result.get("ni_library_queried") is not False):
        raise RuntimeError("Cold-import probe contract mismatch")
    result["probe_pid"] = process.pid
    result["stderr"] = stderr.decode("utf-8", "replace")[-2000:]
    return result


def stage(destination=None, base=BASE, packages=PACKAGES, vc_runtime=VC_RUNTIME, probe_timeout=30.):
    installer = _installer()
    destination = os.path.abspath(destination or os.path.join(tempfile.gettempdir(), "elyse-python34-runtime-" + uuid.uuid4().hex))
    if os.path.exists(destination):
        raise ValueError("Fresh staging directory required; existing files preserved")
    runtime = os.path.join(destination, "runtime")
    os.makedirs(runtime)
    natives = []
    for source, relative in runtime_sources(base, packages, vc_runtime):
        target = installer.safe_path(runtime, relative)
        if not os.path.isdir(os.path.dirname(target)):
            os.makedirs(os.path.dirname(target))
        shutil.copy2(source, target)
        if os.path.splitext(target)[1].lower() in NATIVE_EXTENSIONS:
            machine = pe_machine(target)
            if machine != 0x14c:
                raise ValueError("Non-x86 executable refused: " + relative)
            natives.append(relative)
    _text(os.path.join(runtime, "verify_portable_runtime.py"), PROBE)
    _text(os.path.join(runtime, "PORTABLE_RUNTIME_README.rst"),
        "ELYSE portable application runtime\n==================================\n\n"
        "CPython 3.4.4 x86; NumPy 1.15.4; nidaqmx 0.5.7; six 1.16.0.\n"
        "Launch application shortcuts with pythonw.exe -B to avoid bytecode changes.\n"
        "No PATH/registry change, package manager, hardware initialization or NI runtime installation.\n"
        "NI-DAQmx/NI-IMAQ device drivers must already exist on the target computer.\n"
        "Cold import verification is not target-XP or device-driver qualification.\n"
        "Original Python/Tcl/Tk, NumPy/OpenBLAS and six license notices are preserved.\n"
        "The local nidaqmx wheel provides MIT metadata but no standalone license file;\n"
        "its original METADATA and DESCRIPTION.rst are retained without inventing a notice.\n")
    rows = []
    for root, directories, files in os.walk(runtime):
        for name in files:
            path = os.path.join(root, name)
            rows.append(dict(path=os.path.relpath(path, runtime).replace(os.sep, "/"),
                             sha256=installer.digest(path), bytes=os.path.getsize(path)))
    rows.sort(key=lambda row: row["path"])
    manifest = dict(schema_version=1, role=installer.ROLE,
        python=dict(version="3.4.4", bits=32, implementation="CPython"), packages=dict(PINS),
        files=rows, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        auto_initialize=False, changes_system_configuration=False,
        target_directory=installer.TARGET, launch_flags=["-B"],
        native_architecture="IMAGE_FILE_MACHINE_I386", native_files=natives,
        license_notices=["LICENSE.txt", "Lib/site-packages/numpy/LICENSE.txt", "Lib/site-packages/six-1.16.0.dist-info/LICENSE"],
        nidaqmx_license_evidence="Original wheel METADATA identifies MIT; no standalone license file supplied by that wheel",
        deployment_limits=["Cold imports verified only on the development host", "No NI driver loaded or queried", "Target XP/device qualification remains separate"])
    manifest["manifest_id"] = installer.manifest_identity(manifest)
    installer.verify_files(runtime, manifest)
    probe = probe_runtime(runtime, timeout=probe_timeout)
    installer.verify_files(runtime, manifest)  # Probe must not modify the staged runtime.
    with zipfile.ZipFile(os.path.join(destination, "runtime.zip"), "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in rows:
            archive.write(installer.safe_path(runtime, row["path"]), row["path"])
    manifest["archive"] = dict(path="runtime.zip", sha256=installer.digest(os.path.join(destination, "runtime.zip")))
    installer._write_json(os.path.join(destination, "runtime_manifest.json"), manifest)
    installer._write_json(os.path.join(destination, "cold_probe_result.json"), probe)
    shutil.copy2(os.path.join(os.path.dirname(os.path.abspath(__file__)), "install_xp_python34_runtime.pyw"),
                 os.path.join(destination, "install_xp_python34_runtime.pyw"))
    installer.load_manifest(destination)
    result = dict(folder=destination, runtime=runtime, archive=os.path.join(destination, "runtime.zip"),
        installer=os.path.join(destination, "install_xp_python34_runtime.pyw"),
        manifest_id=manifest["manifest_id"], files=len(rows), total_bytes=sum(row["bytes"] for row in rows),
        archive_bytes=os.path.getsize(os.path.join(destination, "runtime.zip")), cold_probe=probe,
        installation_result=os.path.join(destination, "python34_installation_result.json"),
        hardware_commands_sent=False, xp_changed=False)
    installer._write_json(os.path.join(tempfile.gettempdir(), "elyse-python34-runtime-staging.json"), result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination")
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--packages", default=PACKAGES)
    parser.add_argument("--vc-runtime", default=VC_RUNTIME)
    parser.add_argument("--probe-timeout", type=float, default=30.)
    arguments = parser.parse_args()
    print(json.dumps(stage(arguments.destination, arguments.base, arguments.packages,
                           arguments.vc_runtime, arguments.probe_timeout)))
