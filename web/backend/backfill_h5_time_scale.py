import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Optional

try:
    import h5py
except ImportError:  # pragma: no cover
    h5py = None

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from treatment_network_path import (  # noqa: E402
    copy_local_file_to_smb_atomic,
    copy_smb_file_to_local,
    is_mapped_smb_path,
    is_smb_path,
    normalize_smb_path,
    smb_join,
    smb_listdir,
    smb_to_local_path,
)

TIME_SCALE_PATH_RE = re.compile(
    r"(?<![A-Za-z])(?:\d+(?:\.\d+)?)\s*(fs|ps|ns|us|µs|ms|s)(?![A-Za-z])",
    re.IGNORECASE,
)


def infer_time_scale_from_path(path: str) -> str:
    match = TIME_SCALE_PATH_RE.search(str(path or "").replace("\\", "/"))
    if not match:
        return ""
    return match.group(1).replace("µ", "u").lower()


def _as_text(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if hasattr(value, "item"):
        try:
            return _as_text(value.item())
        except Exception:
            pass
    return str(value or "")


def current_time_scale(local_h5: Path) -> str:
    if h5py is None:
        raise RuntimeError("h5py is not available")
    with h5py.File(local_h5, "r") as h5_file:
        if "metadata" not in h5_file:
            return ""
        metadata = h5_file["metadata"]
        for attr_name in ("time_scale", "scaling_yunit"):
            if attr_name in metadata.attrs:
                value = _as_text(metadata.attrs[attr_name]).strip()
                if value and value != "??":
                    return value
        return ""


def patch_local_h5_time_scale(local_h5: Path, time_scale: str) -> Dict[str, object]:
    if h5py is None:
        raise RuntimeError("h5py is not available")
    with h5py.File(local_h5, "a") as h5_file:
        metadata = h5_file.require_group("metadata")
        before = {
            "time_scale": _as_text(metadata.attrs.get("time_scale", "")),
            "scaling_yunit": _as_text(metadata.attrs.get("scaling_yunit", "")),
        }
        metadata.attrs["time_scale"] = str(time_scale)
        metadata.attrs["scaling_yunit"] = str(time_scale)
    return before


def _iter_local_h5_files(folder: Path) -> Iterable[str]:
    for path in folder.rglob("*.h5"):
        if path.is_file():
            yield str(path)


def _iter_smb_h5_files(folder: str) -> Iterable[str]:
    mapped = smb_to_local_path(folder) if is_mapped_smb_path(folder) else None
    if mapped and os.path.isdir(mapped):
        mapped_root = Path(mapped)
        for local_path in mapped_root.rglob("*.h5"):
            if local_path.is_file():
                relative = local_path.relative_to(mapped_root).as_posix()
                yield smb_join(folder, relative)
        return

    stack = [normalize_smb_path(folder)]
    while stack:
        current = stack.pop()
        for entry in smb_listdir(current):
            entry_path = str(entry["path"])
            if entry.get("is_dir"):
                stack.append(entry_path)
            elif entry.get("is_file") and entry_path.lower().endswith(".h5"):
                yield entry_path


def iter_h5_files(folder: str) -> Iterable[str]:
    if is_smb_path(folder):
        yield from _iter_smb_h5_files(folder)
    else:
        yield from _iter_local_h5_files(Path(folder).expanduser())


def _local_path_for_update(path: str) -> Optional[Path]:
    if is_smb_path(path):
        mapped = smb_to_local_path(path) if is_mapped_smb_path(path) else None
        if mapped and os.path.isfile(mapped):
            return Path(mapped)
        return None
    return Path(path).expanduser()


def repair_h5_time_scale(path: str, apply: bool = False) -> Dict[str, object]:
    time_scale = infer_time_scale_from_path(path)
    if not time_scale:
        return {"path": path, "status": "skipped", "reason": "no time scale in path"}

    local_path = _local_path_for_update(path)
    if local_path is not None:
        existing = current_time_scale(local_path)
        if existing == time_scale:
            return {"path": path, "status": "ok", "time_scale": time_scale}
        if not apply:
            return {
                "path": path,
                "status": "would_update",
                "from": existing or "missing",
                "to": time_scale,
            }
        before = patch_local_h5_time_scale(local_path, time_scale)
        return {"path": path, "status": "updated", "from": before, "to": time_scale}

    with tempfile.TemporaryDirectory(prefix="pyconlyse_h5_timescale_") as tmp_dir:
        local_copy = Path(tmp_dir) / Path(path.replace("\\", "/")).name
        copy_smb_file_to_local(path, local_copy)
        existing = current_time_scale(local_copy)
        if existing == time_scale:
            return {"path": path, "status": "ok", "time_scale": time_scale}
        if not apply:
            return {
                "path": path,
                "status": "would_update",
                "from": existing or "missing",
                "to": time_scale,
            }
        before = patch_local_h5_time_scale(local_copy, time_scale)
        copy_local_file_to_smb_atomic(local_copy, path)
        return {"path": path, "status": "updated", "from": before, "to": time_scale}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill H5 metadata time_scale/scaling_yunit from folder names."
    )
    parser.add_argument("folder", help="Local folder or smb:// folder to scan recursively")
    parser.add_argument("--apply", action="store_true", help="Write metadata updates")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N H5 files")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only final counts and error details.",
    )
    args = parser.parse_args()

    counts: Dict[str, int] = {}
    for index, path in enumerate(iter_h5_files(args.folder), start=1):
        if args.limit and index > args.limit:
            break
        try:
            result = repair_h5_time_scale(path, apply=args.apply)
        except Exception as exc:
            result = {"path": path, "status": "error", "error": str(exc)}
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
        if status == "error" or (
            not args.summary_only and status in {"would_update", "updated", "skipped"}
        ):
            print(result)

    print({"counts": counts, "apply": bool(args.apply)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
