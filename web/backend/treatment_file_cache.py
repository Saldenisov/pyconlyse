import hashlib
import os
import shutil
from pathlib import Path
from typing import Dict, Iterable, Optional


DEFAULT_CACHE_LIMIT_BYTES = 1024 * 1024 * 1024


def get_cache_root() -> Path:
    raw_root = os.environ.get("PYCONLYSE_TREATMENT_CACHE_DIR")
    if raw_root:
        return Path(raw_root).expanduser().resolve()
    return (Path.home() / ".pyconlyse" / "treatment_cache").resolve()


def get_cache_limit_bytes() -> int:
    raw_limit = os.environ.get("PYCONLYSE_TREATMENT_CACHE_LIMIT_BYTES")
    if not raw_limit:
        return DEFAULT_CACHE_LIMIT_BYTES
    try:
        limit = int(raw_limit)
    except ValueError:
        return DEFAULT_CACHE_LIMIT_BYTES
    return max(0, limit)


def is_within_cache(path: str) -> bool:
    try:
        cache_root = get_cache_root()
        candidate = Path(path).expanduser().resolve()
        return os.path.commonpath([str(candidate), str(cache_root)]) == str(cache_root)
    except (OSError, ValueError):
        return False


def _source_digest(source_path: Path) -> str:
    payload = str(source_path.resolve()).encode("utf-8", errors="surrogateescape")
    return hashlib.sha256(payload).hexdigest()[:20]


def _source_id_digest(source_id: str) -> str:
    payload = str(source_id).encode("utf-8", errors="surrogateescape")
    return hashlib.sha256(payload).hexdigest()[:20]


def _iter_cache_files(cache_root: Path) -> Iterable[Path]:
    if not cache_root.exists():
        return []
    return (path for path in cache_root.rglob("*") if path.is_file())


def cache_size_bytes(cache_root: Optional[Path] = None) -> int:
    root = cache_root or get_cache_root()
    total = 0
    for path in _iter_cache_files(root):
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def prune_cache(
    cache_root: Optional[Path] = None,
    limit_bytes: Optional[int] = None,
    keep_paths: Optional[Iterable[Path]] = None,
) -> Dict[str, object]:
    root = cache_root or get_cache_root()
    limit = get_cache_limit_bytes() if limit_bytes is None else max(0, int(limit_bytes))
    keep = {path.resolve() for path in (keep_paths or [])}
    files = []

    for path in _iter_cache_files(root):
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append((path, stat.st_size, stat.st_atime, stat.st_mtime))

    total = sum(item[1] for item in files)
    removed = []
    for path, size, atime, mtime in sorted(files, key=lambda item: (item[2], item[3])):
        if total <= limit:
            break
        if path.resolve() in keep:
            continue
        try:
            path.unlink()
        except OSError:
            continue
        total -= size
        removed.append(str(path))

    for folder in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if folder.is_dir():
            try:
                folder.rmdir()
            except OSError:
                pass

    return {
        "cache_root": str(root),
        "limit_bytes": limit,
        "size_bytes": total,
        "removed": removed,
    }


def cache_file(
    source_path: str,
    cache_root: Optional[Path] = None,
    limit_bytes: Optional[int] = None,
) -> Dict[str, object]:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Source file does not exist")

    root = cache_root or get_cache_root()
    root.mkdir(parents=True, exist_ok=True)

    target_dir = root / _source_digest(source)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name

    source_stat = source.stat()
    needs_copy = True
    if target.exists():
        try:
            target_stat = target.stat()
            needs_copy = (
                target_stat.st_size != source_stat.st_size
                or int(target_stat.st_mtime) < int(source_stat.st_mtime)
            )
        except OSError:
            needs_copy = True

    if needs_copy:
        temp_target = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(source, temp_target)
        os.replace(temp_target, target)

    os.utime(target, None)
    prune_summary = prune_cache(root, limit_bytes, keep_paths=[target])

    return {
        "source_path": str(source),
        "cached_path": str(target),
        "copied": needs_copy,
        "size_bytes": int(target.stat().st_size),
        "cache": prune_summary,
    }


def cache_external_file(
    source_id: str,
    file_name: str,
    copy_to_path,
    cache_root: Optional[Path] = None,
    limit_bytes: Optional[int] = None,
) -> Dict[str, object]:
    root = cache_root or get_cache_root()
    root.mkdir(parents=True, exist_ok=True)

    target_dir = root / _source_id_digest(source_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / Path(file_name).name
    temp_target = target.with_suffix(target.suffix + ".tmp")

    copy_to_path(temp_target)
    os.replace(temp_target, target)
    os.utime(target, None)
    prune_summary = prune_cache(root, limit_bytes, keep_paths=[target])

    return {
        "source_path": source_id,
        "cached_path": str(target),
        "copied": True,
        "size_bytes": int(target.stat().st_size),
        "cache": prune_summary,
    }
