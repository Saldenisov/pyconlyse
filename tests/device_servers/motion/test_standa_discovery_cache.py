import json

from DeviceServers.motion.standa.discovery_cache import (
    load_cached_uri,
    load_discovery_map,
    load_discovery_snapshot,
    store_discovery_map,
)


def test_discovery_cache_round_trip(tmp_path):
    path = tmp_path / "standa.json"

    store_discovery_map({15731: b"xi-com:\\\\.\\COM8"}, path=path)

    assert load_cached_uri(15731, 30.0, path=path) == b"xi-com:\\\\.\\COM8"


def test_discovery_cache_rejects_stale_file(tmp_path):
    path = tmp_path / "standa.json"
    path.write_text(
        json.dumps({"version": 1, "devices": {"15731": "xi-com:test"}}),
        encoding="utf-8",
    )

    assert (
        load_discovery_snapshot(
            30.0, path=path, now=path.stat().st_mtime + 31.0
        )
        is None
    )


def test_discovery_cache_ignores_malformed_content(tmp_path):
    path = tmp_path / "standa.json"
    path.write_text("not json", encoding="utf-8")

    assert load_discovery_map(30.0, path=path) == {}
    assert load_discovery_snapshot(30.0, path=path) is None
