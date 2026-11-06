"""Short-lived, reviewed acquisition destinations. Filesystem reads only.

Replacement writes a fresh version; the manifest selects it only on completion.
No existing HIS/H5 is moved, overwritten or deleted by this planner.
"""
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from threading import RLock
import time
from uuid import uuid4

from vd2_measurement_protocol import Vd2ProtocolError
from vd2_project_manifest import MANIFEST_NAME, load_manifest


def _stat(path):
    try:
        info = path.stat()
        return (info.st_size, info.st_mtime_ns, info.st_ino)
    except FileNotFoundError:
        return None


def _inside(root, path):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise Vd2ProtocolError("Acquisition destination escapes the project folder")
    return path


class PhaseDestinations:
    def __init__(self, ttl=300, maximum=128, clock=time.monotonic):
        self.ttl, self.maximum, self.clock = ttl, maximum, clock
        self._plans = OrderedDict()
        self._lock = RLock()

    @staticmethod
    def _snapshot(request):
        root = Path(request.output_root)
        folder = _inside(root, root / request.run_name)
        manifest = root / MANIFEST_NAME
        data = load_manifest(manifest) if manifest.exists() else {"samples": {}, "artifacts": {}}
        source = _inside(root, Path(request.his_path))
        sample = data["samples"].get(request.run_name, {})
        selected = sample.get("phases", {}).get(request.phase)
        artifact = data["artifacts"].get(selected)
        if artifact and (artifact.get("sample") != request.run_name or artifact.get("phase") != request.phase):
            raise Vd2ProtocolError("Selected manifest phase is inconsistent")
        # Conversion of another phase legitimately updates the manifest and
        # directory timestamps while this destination is being reviewed.
        # Bind only the selected phase and its files; the reserved target
        # directory is rechecked independently before acquisition.
        files = (artifact.get("his", {}).get("path"),) if artifact else (_stat(source), _stat(source.with_suffix(".h5")))
        # A tracked acquisition may finish H5 publication and retire its HIS
        # during review. Its identity/path remain stable, and replacement uses
        # a fresh directory. Untracked files still require exact stat matching.
        signature = (data.get("project_id"), selected, sample.get("repeat_series"), files)
        return root, folder, data, signature

    def review(self, request):
        root, folder, data, signature = self._snapshot(request)
        sample = data["samples"].get(request.run_name, {})
        previous = sample.get("phases", {}).get(request.phase)
        conflict = bool(previous or Path(request.his_path).exists() or Path(request.his_path).with_suffix(".h5").exists())
        choices = {}
        targets = {}
        if not conflict:
            targets["record"] = request
        else:
            version = 2
            parent = folder / ".versions" / request.phase
            while (parent / str(version)).exists():
                version += 1
            revised = _inside(root, parent / str(version) / Path(request.his_path).name)
            targets["replace"] = replace(request, his_path=str(revised), replaces_artifact=previous, reserve_directory=True)
            series = sample.get("repeat_series") or request.run_name
            # The series name comes only from the validated manifest; reject a
            # corrupt path component before considering filesystem candidates.
            if Path(series).name != series or not series or any(char in series for char in '/\\:'):
                raise Vd2ProtocolError("Invalid repeat folder series")
            number = 2
            def numbered(index):
                suffix = f"_{index}"
                return series[:120-len(suffix)].rstrip(". ") + suffix
            while (root / numbered(number)).exists() or numbered(number) in data["samples"]:
                number += 1
            name = numbered(number)
            destination = _inside(root, root / name / Path(request.his_path).name)
            targets["new_folder"] = replace(request, run_name=name, his_path=str(destination), repeat_of=request.run_name,
                                             repeat_series=series, reserve_directory=True)
        with self._lock:
            current = self.clock()
            self._plans = OrderedDict((key, value) for key, value in self._plans.items() if current - value["created"] <= self.ttl)
            for action, target in targets.items():
                token = uuid4().hex
                self._plans[token] = {"original": request, "target": target, "signature": signature, "created": current}
                choices[action] = {"token": token, "run_name": target.run_name, "his_path": target.his_path}
            while len(self._plans) > self.maximum:
                self._plans.popitem(last=False)
        return {"conflict": conflict, "phase": request.phase, "run_name": request.run_name,
                "sample_folder": str(folder), "choices": choices}

    def resolve(self, token, request):
        if not isinstance(token, str) or len(token) != 32:
            raise Vd2ProtocolError("Destination review expired; review the measurement again")
        with self._lock:
            plan = self._plans.get(token)
            if not plan or self.clock() - plan["created"] > self.ttl:
                raise Vd2ProtocolError("Destination review expired; review the measurement again")
            if plan["original"] != request:
                raise Vd2ProtocolError("Measurement settings changed after review; review again")
            return plan["target"]

    def consume(self, token, request):
        with self._lock:
            target = self.resolve(token, request)
            plan = self._plans.pop(token)
        root, _, _, signature = self._snapshot(request)
        if signature != plan["signature"]:
            raise Vd2ProtocolError("Project changed after review; review the measurement again")
        _inside(root, Path(target.his_path))
        if target.reserve_directory and Path(target.his_path).parent.exists():
            raise Vd2ProtocolError("Destination folder was claimed; review the measurement again")
        return target
