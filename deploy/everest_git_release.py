"""Deploy Git revisions of Pyconlyse on Everest before the web server starts."""

import argparse
import hashlib
import json
import msvcrt
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path, PureWindowsPath


FRONTEND = "web/frontend"
BUILD = FRONTEND + "/build"
SOURCE_REF = "refs/pyconlyse-release/develop"
BOOTSTRAP = {"web/bin/start_pyconlyse_local.ps1", "web/bin/start_pyconlyse_production.bat"}
ARCHIVED = (".tmp", "docs/data-treatment", "Supervision/analysis", "Supervision/integration_analysis")
SHARED = {"DeviceServers", "Treatment", "main_app", "utilities", "gui", "legacy", "bin", "scripts"}


class ReleaseError(Exception):
    pass


class ReleaseBusy(ReleaseError):
    pass


def web_listening():
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", 5000)) == 0


def fingerprint(path):
    if not path.exists():
        return None
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked(root, name):
    """Check every component before accessing a tracked or generated path."""
    parts = name.split("/")
    if not parts or any(not p or p in {".", ".."} or p.endswith((".", " ")) or
                        any(c in p for c in '\\:<>|?*"') or p.casefold() == ".git" or
                        PureWindowsPath(p).is_reserved() for p in parts):
        raise ReleaseError(f"Unsafe path: {name}")
    path = root
    for part in parts:
        path /= part
        try:
            attributes = path.lstat().st_file_attributes
        except FileNotFoundError:
            continue
        if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ReleaseError(f"Reparse point in release path: {path}")
    return path


def root_path(path):
    if not path.is_absolute() or path.resolve() != path:
        raise ReleaseError(f"Expected physical absolute root: {path}")
    return path


def raise_walk_error(error):
    raise error


def tree_hashes(path):
    if path.resolve() != path or not path.is_dir():
        raise ReleaseError(f"Expected a physical directory: {path}")
    result = {}
    for parent, dirs, files in os.walk(path, onerror=raise_walk_error):
        for name in dirs + files:
            item = Path(parent) / name
            relative = item.relative_to(path).as_posix()
            checked(path, relative)
            if name in files:
                result[relative] = fingerprint(item)
    return result


def remove_owned_tree(path, parent, prefix):
    if path.parent != parent or not path.name.startswith(prefix):
        raise ReleaseError(f"Unexpected cleanup path: {path}")
    if path.exists():
        tree_hashes_without_reading(path)
        def retry_readonly(function, filename, error):
            if not isinstance(error, PermissionError):
                raise error
            os.chmod(filename, stat.S_IWRITE)
            function(filename)

        shutil.rmtree(path, onexc=retry_readonly)


def tree_hashes_without_reading(path):
    root_path(path)
    for parent, dirs, files in os.walk(path, onerror=raise_walk_error):
        for name in dirs + files:
            item = Path(parent) / name
            if item.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ReleaseError(f"Reparse point in release tree: {item}")


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pyconlyse-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def write_json(path, data):
    atomic_write(path, (json.dumps(data, sort_keys=True) + "\n").encode())


def read_json(path):
    return json.loads(path.read_bytes())


def archived(path):
    return any(path == root or path.startswith(root + "/") for root in ARCHIVED)


def frontend_input(path):
    return path.startswith(FRONTEND + "/") and not path.startswith(BUILD + "/")


def validate_build(path):
    manifest = read_json(checked(path, "asset-manifest.json"))
    if not checked(path, "index.html").is_file():
        raise ReleaseError(f"Missing index.html in {path}")
    entries = manifest.get("entrypoints") or [manifest["files"]["main.js"]]
    if not entries or any(not checked(path, entry.lstrip("/")).is_file() for entry in entries):
        raise ReleaseError(f"Missing entry point in {path}")


class Deployment:
    def __init__(self, source, runtime, storage, state):
        self.source = root_path(source)
        self.runtime = root_path(runtime)
        self.storage = root_path(storage)
        self.control = root_path(state)
        self.state_file = checked(self.control, "state.json")
        self.pending_file = checked(self.control, "pending.json")
        self.build_path = checked(self.runtime, BUILD)

    def git(self, *args, repo=None, check=True):
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(repo or self.runtime), "-c", "core.longpaths=true",
             "-c", "core.hooksPath=NUL", *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode and check:
            raise ReleaseError(f"git {args[0]}: {result.stderr.decode(errors='replace').strip()}")
        return result

    def git_text(self, *args, **kwargs):
        return self.git(*args, **kwargs).stdout.decode().strip()

    def git_paths(self, *args, **kwargs):
        return [name.decode("utf-8") for name in self.git(*args, **kwargs).stdout.split(b"\0") if name]

    def tree(self, commit):
        entries = {}
        for row in self.git("ls-tree", "-r", "-z", commit).stdout.split(b"\0"):
            if row:
                metadata, name = row.split(b"\t", 1)
                mode, kind, oid = metadata.decode().split()
                entries[name.decode("utf-8")] = (mode, kind, oid)
        return entries

    def initialize(self):
        if self.state_file.exists():
            raise ReleaseError("Deployment state is already initialized.")
        head = self.git_text("rev-parse", "HEAD")
        if head != self.git_text("rev-parse", "refs/heads/develop", repo=self.source):
            raise ReleaseError("Initial runtime HEAD differs from develop on D:.")
        changed = self.git_paths("diff", "--no-renames", "--name-only", "-z", "HEAD", "--")
        # Adopt identical existing web files copied from C to D, even if still untracked.
        untracked = self.git_paths("ls-files", "--others", "--exclude-standard", "-z", "--",
                                   "web/backend", "web/start_local.py", "web/frontend/src",
                                   "web/frontend/public", repo=self.source)
        baseline = {name: fingerprint(checked(self.runtime, name)) for name in changed if not archived(name)}
        for name in untracked:
            local = checked(self.runtime, name)
            if local.is_file() and fingerprint(local) == fingerprint(checked(self.source, name)):
                baseline[name] = fingerprint(local)
        write_json(self.state_file, {"commit": head, "baseline": baseline, "backup": None, "held": None})
        print(f"Initialized at {head}, recorded {len(baseline)} existing local files.")

    def fetch(self, revision):
        self.git("fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                 "--", str(self.source), f"refs/heads/develop:{SOURCE_REF}")
        candidate = self.git_text("rev-parse", "--verify", "--end-of-options",
                                  (revision or SOURCE_REF) + "^{commit}")
        if self.git("merge-base", "--is-ancestor", candidate, SOURCE_REF, check=False).returncode:
            raise ReleaseError("The selected revision must be on develop from D:.")
        return candidate

    def blob_matches(self, path, name, entry):
        if not path.exists():
            return entry is None
        if entry is None or not path.is_file():
            return False
        return self.git_text("hash-object", "--path=" + name, "--", str(path)) == entry[2]

    def plan(self, state, candidate):
        before = state["commit"]
        if self.git("merge-base", "--is-ancestor", before, candidate, check=False).returncode:
            raise ReleaseError("Release must move forward. Use rollback to restore the previous version.")
        old, new = self.tree(before), self.tree(candidate)
        names = self.git_paths("diff", "--no-renames", "--name-only", "-z", before, candidate, "--")
        if len(set(name.casefold() for name in names)) != len(names):
            raise ReleaseError("Windows case collision in release paths.")
        files = {}
        for name in names:
            if archived(name):
                continue
            if name == BUILD or name.startswith(BUILD + "/"):
                raise ReleaseError(f"Generated build must stay outside Git: {name}")
            path = checked(self.runtime, name)
            for entry in (old.get(name), new.get(name)):
                if entry is not None and (entry[0] not in {"100644", "100755"} or entry[1] != "blob"):
                    raise ReleaseError(f"Unsupported Git entry: {name}")
            if self.blob_matches(path, name, new.get(name)):
                continue
            if name in BOOTSTRAP:
                raise ReleaseError(f"Launcher changes require a separate installation: {name}")
            if name in state["baseline"]:
                expected = state["baseline"][name] == fingerprint(path)
            else:
                expected = self.blob_matches(path, name, old.get(name))
            if not expected:
                raise ReleaseError(f"Local edit or untracked file differs from the release baseline: {name}")
            if path.exists() and path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY:
                raise ReleaseError(f"Read-only runtime file: {name}")
            entry = new.get(name)
            files[name] = self.git("cat-file", "blob", entry[2]).stdout if entry else None
        build_needed = any(frontend_input(name) for name in names)
        if build_needed:
            outstanding = sorted(name for name in state["baseline"] if frontend_input(name)
                                 and name not in names and
                                 not self.blob_matches(checked(self.runtime, name), name, new.get(name)))
            if outstanding:
                raise ReleaseError("Commit existing frontend source edits before building a release: "
                                   + ", ".join(outstanding[:8]))
        return names, files, build_needed

    def prepare_build(self, candidate):
        releases = checked(self.storage, "builds")
        releases.mkdir(parents=True, exist_ok=True)
        release = checked(releases, candidate)
        if release.exists():
            build = checked(release, "build")
            if read_json(checked(release, "manifest.json")) != tree_hashes(build):
                raise ReleaseError(f"Cached build fingerprint differs: {candidate}")
            validate_build(build)
            return build

        stage = Path(tempfile.mkdtemp(prefix=".build-", dir=releases))
        try:
            work = checked(stage, "source")
            work.mkdir()
            for name, entry in self.tree(candidate).items():
                if not frontend_input(name):
                    continue
                if entry[0] not in {"100644", "100755"} or entry[1] != "blob":
                    raise ReleaseError(f"Unsupported frontend entry: {name}")
                file = checked(work, name[len(FRONTEND) + 1:])
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(self.git("cat-file", "blob", entry[2]).stdout)
            npm = shutil.which("npm.cmd")
            if not npm:
                raise ReleaseError("npm.cmd is required to build the release on D:.")
            build_env = {key: value for key, value in os.environ.items() if key.upper() in {
                "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "USERPROFILE", "APPDATA",
                "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "USERNAME",
                "USERDOMAIN", "SYSTEMDRIVE", "HOMEDRIVE", "HOMEPATH", "NUMBER_OF_PROCESSORS",
            }}
            temp = checked(stage, "temp")
            temp.mkdir()
            build_env.update(TEMP=str(temp), TMP=str(temp), CI="false")
            cache = checked(self.storage, "npm-cache")
            with checked(stage, "build.log").open("wb") as log:
                for args in (["ci", "--legacy-peer-deps", "--cache", str(cache), "--no-audit", "--no-fund"],
                             ["run", "build", "--cache", str(cache)]):
                    result = subprocess.run([npm, *args], cwd=work, env=build_env,
                                            stdout=log, stderr=subprocess.STDOUT, timeout=1200)
                    if result.returncode:
                        log.flush()
                        tail = checked(stage, "build.log").read_text(errors="replace").splitlines()[-20:]
                        raise ReleaseError("Frontend build failed:\n" + "\n".join(tail))
            build = checked(work, "build")
            validate_build(build)
            manifest = tree_hashes(build)
            ready = checked(stage, "ready")
            ready.mkdir()
            build.rename(checked(ready, "build"))
            write_json(checked(ready, "manifest.json"), manifest)
            root_path(ready)
            root_path(release)
            ready.rename(release)
            return checked(release, "build")
        finally:
            remove_owned_tree(stage, releases, ".build-")

    def offline(self, names, build_changed):
        if not names and not build_changed:
            return
        if web_listening():
            raise ReleaseError("Web server is listening on port 5000. Stop it before applying or rolling back.")
        # A server still importing its app can be active before port 5000 opens.
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                                 "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                                 "Where-Object CommandLine -Match '\\bstart_(local|production)\\.py\\b') { exit 3 }"],
                                capture_output=True)
        if result.returncode:
            raise ReleaseError("A Pyconlyse web process is starting or stopping.")
        if any(name.split("/")[0] in SHARED or "/" not in name for name in names):
            result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                                     "if (Get-Process -Name Starter -ErrorAction SilentlyContinue) { exit 3 }"],
                                    capture_output=True)
            if result.returncode:
                raise ReleaseError("Release changes shared runtime files while Tango Starter is active.")

    def backup(self, state, names, build_changed):
        identity = uuid.uuid4().hex
        backup = checked(self.storage, "backups/" + identity)
        backup.mkdir(parents=True)
        file_hashes = {}
        for name in names:
            live = checked(self.runtime, name)
            digest = fingerprint(live)
            file_hashes[name] = digest
            if digest is not None:
                saved = checked(backup, "files/" + name)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(live, saved)
                if fingerprint(saved) != digest or fingerprint(live) != digest:
                    raise ReleaseError(f"File changed while backing up: {name}")
        build_hashes = None
        if build_changed and self.build_path.exists():
            build_hashes = tree_hashes(self.build_path)
            saved_build = checked(backup, "build")
            shutil.copytree(self.build_path, saved_build)
            if tree_hashes(saved_build) != build_hashes:
                raise ReleaseError("Current build backup differs.")
        for name, digest in file_hashes.items():
            if fingerprint(checked(self.runtime, name)) != digest:
                raise ReleaseError(f"Runtime changed during backup: {name}")
        write_json(checked(backup, "manifest.json"),
                   {"state": state, "files": file_hashes, "build_changed": build_changed, "build": build_hashes})
        return identity

    def backup_data(self, identity):
        if len(identity) != 32 or any(c not in "0123456789abcdef" for c in identity):
            raise ReleaseError("Invalid backup identifier.")
        backup = checked(self.storage, "backups/" + identity)
        info = read_json(checked(backup, "manifest.json"))
        files = {}
        for name, expected in info["files"].items():
            saved = checked(backup, "files/" + name)
            if expected is not None and fingerprint(saved) != expected:
                raise ReleaseError(f"Backup file differs: {name}")
            files[name] = saved.read_bytes() if expected is not None else None
        build = checked(backup, "build") if info["build"] is not None else None
        if build is not None and tree_hashes(build) != info["build"]:
            raise ReleaseError("Backup build fingerprint differs.")
        return info, files, build

    def install(self, files, build_changed, build, identity):
        for name, contents in files.items():
            live = checked(self.runtime, name)
            if contents is None:
                live.unlink(missing_ok=True)
            else:
                atomic_write(live, contents)
        if build_changed:
            parent = self.build_path.parent
            root_path(parent)
            incoming = checked(parent, ".release-in-" + identity)
            outgoing = checked(parent, ".release-out-" + identity)
            remove_owned_tree(incoming, parent, ".release-in-")
            if build is not None:
                expected = tree_hashes(build)
                shutil.copytree(build, incoming)
                if tree_hashes(incoming) != expected:
                    raise ReleaseError("Staged build fingerprint differs.")
            if self.build_path.exists():
                tree_hashes_without_reading(self.build_path)
                if outgoing.exists():
                    remove_owned_tree(outgoing, parent, ".release-out-")
                self.build_path.rename(outgoing)
            if build is not None:
                root_path(incoming)
                incoming.rename(self.build_path)
            remove_owned_tree(outgoing, parent, ".release-out-")

    def recover(self):
        if not self.pending_file.exists():
            return
        identity = read_json(self.pending_file)["backup"]
        info, files, build = self.backup_data(identity)
        self.offline(files, info["build_changed"])
        self.install(files, info["build_changed"], build, identity)
        write_json(self.state_file, info["state"])
        self.pending_file.unlink()
        print(f"Restored interrupted transaction from {identity}.")

    def transaction(self, state, files, build_changed, build, new_state, rollback=False):
        self.offline(files, build_changed)
        identity = self.backup(state, files, build_changed)
        # Check again after a long build backup, before any live file is changed.
        self.offline(files, build_changed)
        write_json(self.pending_file, {"backup": identity})
        self.install(files, build_changed, build, identity)
        if not rollback:
            new_state["backup"] = identity
        write_json(self.state_file, new_state)
        self.pending_file.unlink()
        print(f"Runtime commit {new_state['commit']}. Backup {identity}.")

    def apply(self, state, candidate, action):
        if candidate == state["commit"] or (action == "auto" and candidate == state["held"]):
            print(f"No release to install. Runtime commit {state['commit']}.")
            return
        names, files, build_needed = self.plan(state, candidate)
        print(f"{state['commit'][:12]} -> {candidate[:12]}: {len(files)} file changes, frontend build={build_needed}.",
              flush=True)
        if action == "check":
            return
        if action != "prepare":
            self.offline(files, build_needed)
        build = self.prepare_build(candidate) if build_needed else None
        if action == "prepare":
            print(f"Prepared {candidate}.")
            return
        # Building can take several minutes. Recheck local files before taking the backup.
        names, files, build_needed = self.plan(state, candidate)
        baseline = {key: value for key, value in state["baseline"].items() if key not in names}
        new_state = {"commit": candidate, "baseline": baseline, "backup": None, "held": None}
        self.transaction(state, files, build_needed, build, new_state)

    def rollback(self, state):
        if not state["backup"]:
            raise ReleaseError("There is no previous deployed version to restore.")
        info, files, build = self.backup_data(state["backup"])
        previous = {**info["state"], "held": state["commit"]}
        self.transaction(state, files, info["build_changed"], build, previous, rollback=True)

    def start_web(self, production):
        web_root = checked(self.runtime, "web")
        if not checked(self.runtime, BUILD + "/index.html").is_file():
            raise ReleaseError("The frontend build is missing from C:.")
        entry = "start_production.py" if production else "start_local.py"
        if production:
            log_dir = Path(os.environ["ProgramData"]) / "Pyconlyse"
            log_name, error_name = "web-production.log", None
        else:
            log_dir = Path(os.environ["LOCALAPPDATA"]) / "Pyconlyse" / "logs"
            log_name, error_name = "web-local.log", "web-local-error.log"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / log_name).open("ab" if production else "wb") as output:
            if error_name:
                with (log_dir / error_name).open("wb") as errors:
                    process = subprocess.Popen([sys.executable, "-u", entry], cwd=web_root,
                                               stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                process = subprocess.Popen([sys.executable, entry], cwd=web_root,
                                           stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ReleaseError(f"Web process exited with code {process.returncode}; see {log_dir}.")
            if web_listening():
                print(f"Pyconlyse is listening on port 5000 (PID {process.pid}).")
                return
            time.sleep(0.5)
        print(f"Pyconlyse process {process.pid} is still starting; see {log_dir}.")

    def launch(self, state, production):
        if web_listening():
            print("Port 5000 is already listening.")
            return
        try:
            self.apply(state, self.fetch(None), "auto")
        except (OSError, ValueError, KeyError, ReleaseError, subprocess.SubprocessError) as exc:
            if self.pending_file.exists():
                self.recover()
            print(f"Release deferred: {exc}", file=sys.stderr)
        installed = read_json(self.state_file)
        try:
            self.start_web(production)
        except (OSError, ReleaseError):
            if installed["commit"] == state["commit"]:
                raise
            print("New web process failed during startup. Restoring the previous release.", file=sys.stderr)
            self.rollback(installed)
            self.start_web(production)

    def run(self, action, revision):
        self.control.mkdir(parents=True, exist_ok=True)
        lock = checked(self.control, "deployment.lock")
        with lock.open("a+b") as handle:
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ReleaseBusy("A deployment command is already running.") from exc
            try:
                self.recover()
                if action == "initialize":
                    self.initialize()
                    return
                state = read_json(self.state_file)
                if action == "status":
                    print(json.dumps({key: value for key, value in state.items() if key != "baseline"}, indent=2))
                elif action == "rollback":
                    self.rollback(state)
                elif action in {"launch-local", "launch-production"}:
                    self.launch(state, action == "launch-production")
                else:
                    self.apply(state, self.fetch(revision), action)
            except Exception:
                if self.pending_file.exists():
                    self.recover()
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "status", "check", "prepare", "apply", "auto", "rollback",
                                           "launch-local", "launch-production"))
    parser.add_argument("revision", nargs="?")
    parser.add_argument("--source", type=Path, default=Path(r"D:\dev\pyconlyse"))
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\dev\pyconlyse"))
    parser.add_argument("--storage", type=Path, default=Path(r"D:\dev\pyconlyse-releases"))
    parser.add_argument("--state", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    deployment = None
    try:
        deployment = Deployment(args.source, args.runtime, args.storage, args.state)
        deployment.run(args.action, args.revision)
    except (OSError, ValueError, KeyError, ReleaseError, subprocess.SubprocessError) as exc:
        print(f"Pyconlyse release: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, ReleaseBusy) or (deployment and deployment.pending_file.exists()) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())






