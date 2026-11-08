import copy
import sqlite3
import uuid

import pytest

from web.backend.vd2_alignment_presets import (
    AlignmentSnapshots, CHANNELS, DEVICE, SnapshotConflict, validate_intent,
)


def channels(value=0):
    ids = [1, 3, 5, 6, 7, 9, 11, 12]
    return [dict(id=slot, name=name, value=value, measured=value, min=-15, max=15, state=1)
            for slot, name in zip(ids, CHANNELS)]


def intent(kind="before_search", value=0, **extra):
    return validate_intent(dict(device=DEVICE, kind=kind, operation_id=str(uuid.uuid4()),
                                expected=channels(value), **extra))


def test_persists_best_and_return_points_across_instances_without_replacing_state(tmp_path):
    path = tmp_path / "application.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE state(key TEXT PRIMARY KEY,value TEXT)")
        db.execute("INSERT INTO state VALUES('active_job','untouched')")
    repo = AlignmentSnapshots(path)
    assert repo.history(DEVICE)["recommended"] is None
    before = repo.capture(intent(), channels())
    assert AlignmentSnapshots(path).history(DEVICE)["recommended"]["id"] == before["id"]
    best = repo.capture(intent("manual_best", 1), channels(1))
    later = repo.capture(intent(value=2), channels(2))
    history = AlignmentSnapshots(path).history(DEVICE)
    assert history["recommended"] == best
    assert history["previous"] == later
    assert len(history["history"]) == 3
    assert best["created_at"].endswith("+00:00")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM state WHERE key='active_job'").fetchone()[0] == "untouched"


def test_completed_search_retains_parent_and_statistics_and_older_best(tmp_path):
    repo = AlignmentSnapshots(tmp_path / "db")
    old = repo.capture(intent("manual_best"), channels())
    before = repo.capture(intent(), channels())
    best = repo.capture(intent("search_best", 0.05, parent_id=before["id"], quality=dict(mean=12, sd=0.4, n=15)), channels(0.05))
    assert repo.history(DEVICE)["best"] == best
    assert best["parent_id"] == before["id"]
    assert any(item["id"] == old["id"] for item in repo.history(DEVICE)["history"])
    with pytest.raises(ValueError, match="before-search"):
        repo.preflight(intent("search_best", parent_id=old["id"], quality=dict(mean=1, sd=0, n=3)))
    with pytest.raises(ValueError, match="missing"):
        repo.preflight(intent("before_restore", parent_id="missing"))


def test_idempotent_save_returns_one_record_and_conflicting_replay_is_rejected(tmp_path):
    repo = AlignmentSnapshots(tmp_path / "db")
    request = intent()
    saved = repo.capture(request, channels())
    assert repo.preflight(request) == saved
    assert repo.capture(request, channels()) == saved
    assert len(repo.history(DEVICE)["history"]) == 1
    changed = copy.deepcopy(request)
    changed["context"] = {"changed": True}
    with pytest.raises(SnapshotConflict, match="different settings"):
        repo.preflight(changed)


@pytest.mark.parametrize("mutate", [
    lambda data: data[7].update(state=0), lambda data: data[7].update(measured=0.1),
    lambda data: data[7].update(max=-1), lambda data: data[7].update(id=1),
    lambda data: data[7].update(name="other"), lambda data: data[7].update(value=float("nan")),
    lambda data: data[7].update(value=True),
])
def test_invalid_or_unsettled_vector_never_replaces_best(tmp_path, mutate):
    repo = AlignmentSnapshots(tmp_path / "db")
    best = repo.capture(intent("manual_best"), channels())
    invalid = channels()
    mutate(invalid)
    with pytest.raises(ValueError):
        repo.capture(intent("manual_best"), invalid)
    assert repo.history(DEVICE)["best"] == best
    assert len(repo.history(DEVICE)["history"]) == 1


def test_changed_currents_or_ids_after_review_do_not_save(tmp_path):
    repo = AlignmentSnapshots(tmp_path / "db")
    with pytest.raises(SnapshotConflict, match="changed after review"):
        repo.capture(intent(), channels(0.05))
    changed = channels()
    changed[0]["id"] = 100
    with pytest.raises(SnapshotConflict):
        repo.capture(intent(), changed)
    assert repo.history(DEVICE)["history"] == []


def test_database_unavailable_fails_instead_of_using_volatile_memory(tmp_path):
    path = tmp_path / "directory"
    path.mkdir()
    with pytest.raises(sqlite3.OperationalError):
        AlignmentSnapshots(path).capture(intent(), channels())


def test_failed_transaction_preserves_existing_best(tmp_path):
    path = tmp_path / "db"
    repo = AlignmentSnapshots(path)
    best = repo.capture(intent("manual_best"), channels())
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER fail_save BEFORE INSERT ON vd2_alignment_snapshots BEGIN SELECT RAISE(ABORT,'disk failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="disk failure"):
        repo.capture(intent("manual_best", 1), channels(1))
    assert repo.history(DEVICE)["best"] == best
    assert len(repo.history(DEVICE)["history"]) == 1


@pytest.mark.parametrize("patch", [
    dict(kind="wrong"), dict(device="other/device/1"), dict(operation_id="bad"),
    dict(context={"nan": float("nan")}), dict(kind="search_best"),
    dict(kind="search_best", parent_id="x", quality=dict(mean=1, sd=0, n=1)),
])
def test_invalid_intent_is_rejected(patch):
    data = dict(device=DEVICE, kind="manual_best", operation_id=str(uuid.uuid4()), expected=channels())
    data.update(patch)
    with pytest.raises(ValueError):
        validate_intent(data)
