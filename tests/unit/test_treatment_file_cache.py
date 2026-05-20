import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from treatment_file_cache import cache_file, cache_size_bytes, is_within_cache, prune_cache


def test_cache_file_copies_source_and_reuses_current_copy(tmp_path, monkeypatch):
    source = tmp_path / "source" / "ABS001.his"
    source.parent.mkdir()
    source.write_bytes(b"abc")
    cache_root = tmp_path / "cache"
    monkeypatch.setenv("PYCONLYSE_TREATMENT_CACHE_DIR", str(cache_root))

    first = cache_file(str(source), cache_root=cache_root, limit_bytes=1024)
    second = cache_file(str(source), cache_root=cache_root, limit_bytes=1024)
    cached_path = Path(first["cached_path"])

    assert cached_path.is_file()
    assert cached_path.read_bytes() == b"abc"
    assert first["copied"] is True
    assert second["copied"] is False
    assert second["cached_path"] == first["cached_path"]
    assert is_within_cache(str(cached_path)) is True


def test_prune_cache_removes_oldest_files_but_keeps_requested_path(tmp_path):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    old_file = cache_root / "old.bin"
    keep_file = cache_root / "keep.bin"
    old_file.write_bytes(b"1" * 80)
    keep_file.write_bytes(b"2" * 80)

    old_time = 1_700_000_000
    new_time = 1_700_001_000
    os.utime(old_file, (old_time, old_time))
    os.utime(keep_file, (new_time, new_time))

    summary = prune_cache(cache_root, limit_bytes=90, keep_paths=[keep_file])

    assert keep_file.is_file()
    assert not old_file.exists()
    assert summary["size_bytes"] == 80
    assert cache_size_bytes(cache_root) == 80
