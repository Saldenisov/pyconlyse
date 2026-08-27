"""Deterministic contracts for the software-only treatment queue runner."""

import sys
import time
from pathlib import Path
from threading import Event, Lock

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from treatment_api import TreatmentQueueStore


def _wait_for(event, timeout=2.0):
    """Wait on a controllable event without polling queue timing."""
    assert event.wait(timeout), "queue worker did not reach expected state"


def _wait_until(predicate, timeout=2.0):
    """Wait for a state transition using the queue's observable snapshot."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate(), "queue did not reach expected state"


def _named_recipe(name):
    return {
        "name": name,
        "output": {"path": f"/tmp/{name}.dat"},
    }


def test_enqueue_freezes_recipe_before_later_session_edits():
    queue = TreatmentQueueStore()
    recipe = {
        "paths": {"ABS": "/data/abs-a.h5"},
        "config": {
            "convert_to_h5": True,
            "cleaning": {"enabled": True, "angle_threshold": 1.5},
        },
    }

    job = queue.enqueue("session-immutable", recipe)

    # Simulate later edits in the live session and in caller-owned payloads.
    recipe["paths"]["ABS"] = "/data/abs-b.h5"
    recipe["config"]["cleaning"]["angle_threshold"] = 99.0

    stored = queue.snapshot("session-immutable")["jobs"][0]
    assert stored["job_id"] == job["job_id"]
    assert stored["recipe"] == {
        "paths": {"ABS": "/data/abs-a.h5"},
        "config": {
            "convert_to_h5": True,
            "cleaning": {"enabled": True, "angle_threshold": 1.5},
        },
    }


def test_enqueue_has_no_processing_side_effects():
    queue = TreatmentQueueStore()
    calls = []

    def executor(job_id, recipe):
        calls.append((job_id, recipe))
        return {"result": {"ok": True}}

    queued = queue.enqueue("session-side-effects", {"paths": {"ABS": "a.h5"}})

    assert calls == []
    snapshot = queue.snapshot("session-side-effects")
    assert snapshot["running"] is False
    assert snapshot["pending_count"] == 1
    assert snapshot["jobs"][0]["status"] == "queued"
    assert snapshot["jobs"][0]["job_id"] == queued["job_id"]


def test_queue_reserves_duplicate_output_path_while_pending():
    queue = TreatmentQueueStore()
    queue.enqueue("session-reservation", _named_recipe("first"))

    with pytest.raises(ValueError, match="already reserved"):
        queue.enqueue("session-reservation", _named_recipe("first"))


def test_output_reservation_is_global_and_released_after_queued_removal():
    queue = TreatmentQueueStore()
    first = queue.enqueue(
        "session-a",
        {"output": {"path": "C:/Runs/Result.dat"}},
    )

    with pytest.raises(ValueError, match="already reserved"):
        queue.enqueue(
            "session-b",
            {"output": {"path": r"c:\runs\result.dat"}},
        )

    removed = queue.remove_queued("session-a", first["job_id"])
    assert removed["job_id"] == first["job_id"]
    released = queue.enqueue(
        "session-b",
        {"output": {"path": r"c:\runs\result.dat"}},
    )
    assert released["recipe"]["output"]["path"] == r"c:\runs\result.dat"


def test_queued_and_running_jobs_block_immediate_output_reservation():
    queue = TreatmentQueueStore()
    output_path = "C:/Runs/active.dat"
    job = queue.enqueue("session-queued", {"output": {"path": output_path}})

    with pytest.raises(ValueError, match="already reserved"):
        queue.reserve_immediate_output(output_path)

    entered = Event()
    release = Event()
    finished = Event()

    def executor(_job_id, _recipe):
        entered.set()
        _wait_for(release)
        finished.set()
        return {}

    assert queue.start("session-queued", executor) is True
    _wait_for(entered)
    with pytest.raises(ValueError, match="already reserved"):
        queue.reserve_immediate_output(output_path)
    release.set()
    _wait_for(finished)
    _wait_until(lambda: not queue.snapshot("session-queued")["running"])
    assert job["job_id"]


def test_immediate_save_reservation_blocks_queue_until_released():
    queue = TreatmentQueueStore()
    output_path = "C:/Runs/immediate.dat"
    owner = queue.reserve_immediate_output(output_path)

    with pytest.raises(ValueError, match="already reserved"):
        queue.enqueue("session-queue", {"output": {"path": output_path}})

    queue.release_immediate_output(output_path, owner)
    job = queue.enqueue("session-queue", {"output": {"path": output_path}})
    assert job["status"] == "queued"


@pytest.mark.parametrize("should_fail", [False, True])
def test_terminal_queue_job_releases_output_reservation(should_fail):
    queue = TreatmentQueueStore()
    output_path = "C:/Runs/terminal.dat"
    queue.enqueue("session-terminal", {"output": {"path": output_path}})

    def executor(_job_id, _recipe):
        if should_fail:
            raise RuntimeError("simulated terminal failure")
        return {"result": {"ok": True}}

    assert queue.start("session-terminal", executor) is True
    _wait_until(lambda: not queue.snapshot("session-terminal")["running"])
    owner = queue.reserve_immediate_output(output_path)
    assert owner
    queue.release_immediate_output(output_path, owner)


def test_remove_only_removes_queued_job_and_sessions_are_isolated():
    queue = TreatmentQueueStore()
    first = queue.enqueue("session-a", _named_recipe("a"))
    second = queue.enqueue("session-b", _named_recipe("b"))

    removed = queue.remove_queued("session-a", first["job_id"])
    assert removed["job_id"] == first["job_id"]
    assert queue.snapshot("session-a")["jobs"] == []
    assert queue.snapshot("session-b")["jobs"][0]["job_id"] == second["job_id"]

    entered = Event()
    release = Event()

    def executor(_job_id, _recipe):
        entered.set()
        _wait_for(release)

    active = queue.enqueue("session-a", _named_recipe("active"))
    assert queue.start("session-a", executor) is True
    _wait_for(entered)
    with pytest.raises(RuntimeError, match="Only queued jobs"):
        queue.remove_queued("session-a", active["job_id"])
    release.set()


def test_start_executes_jobs_sequentially_in_enqueue_order():
    queue = TreatmentQueueStore()
    entered_first = Event()
    release_first = Event()
    calls = []
    calls_lock = Lock()

    def executor(job_id, recipe):
        with calls_lock:
            calls.append((job_id, recipe["name"], "entered"))
        if recipe["name"] == "first":
            entered_first.set()
            _wait_for(release_first)
        with calls_lock:
            calls.append((job_id, recipe["name"], "finished"))
        return {"result": {"name": recipe["name"]}}

    first = queue.enqueue("session-sequential", _named_recipe("first"))
    second = queue.enqueue("session-sequential", _named_recipe("second"))
    assert queue.start("session-sequential", executor) is True
    _wait_for(entered_first)

    assert [entry[1] for entry in calls] == ["first"]
    assert queue.snapshot("session-sequential")["jobs"][1]["status"] == "queued"

    release_first.set()
    _wait_until(
        lambda: all(
            item["status"] == "completed"
            for item in queue.snapshot("session-sequential")["jobs"]
        )
    )
    assert [entry[1] for entry in calls if entry[2] == "entered"] == [
        "first",
        "second",
    ]
    sequential_ids = [
        item["job_id"] for item in queue.snapshot("session-sequential")["jobs"]
    ]
    assert sequential_ids == [
        first["job_id"],
        second["job_id"],
    ]


def test_enqueue_while_running_is_drained_after_active_job():
    queue = TreatmentQueueStore()
    entered = Event()
    release = Event()
    entered_names = []

    def executor(_job_id, recipe):
        entered_names.append(recipe["name"])
        if recipe["name"] == "active":
            entered.set()
            _wait_for(release)
        return {"result": recipe["name"]}

    queue.enqueue("session-append", _named_recipe("active"))
    assert queue.start("session-append", executor) is True
    _wait_for(entered)

    appended = queue.enqueue("session-append", _named_recipe("appended"))
    snapshot = queue.snapshot("session-append")
    assert snapshot["active_job_id"]
    assert snapshot["pending_count"] == 1
    assert next(
        item for item in snapshot["jobs"] if item["job_id"] == appended["job_id"]
    )["status"] == "queued"

    release.set()
    _wait_until(
        lambda: not queue.snapshot("session-append")["running"]
        and all(
            item["status"] == "completed"
            for item in queue.snapshot("session-append")["jobs"]
        )
    )
    assert entered_names == ["active", "appended"]


def test_failed_job_remains_visible_with_error_and_does_not_abort_later_jobs():
    queue = TreatmentQueueStore()
    entered = []

    def executor(_job_id, recipe):
        entered.append(recipe["name"])
        if recipe["name"] == "bad":
            raise RuntimeError("conversion failed")
        return {"result": {"name": recipe["name"]}}

    queue.enqueue("session-failure", _named_recipe("bad"))
    queue.enqueue("session-failure", _named_recipe("good"))
    assert queue.start("session-failure", executor) is True

    _wait_until(lambda: not queue.snapshot("session-failure")["running"])
    jobs = queue.snapshot("session-failure")["jobs"]
    assert entered == ["bad", "good"]
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["error"] == "conversion failed"
    assert jobs[0]["completed_at"]
    assert jobs[1]["status"] == "completed"


def test_queue_executor_surface_is_software_only():
    queue = TreatmentQueueStore()
    hardware_calls = []

    def executor(_job_id, recipe):
        # A queue executor receives only the frozen recipe. Hardware clients
        # are intentionally absent from this software-only boundary.
        assert set(recipe) == {"software_only", "convert_to_h5", "cleaning", "output"}
        return {"result": {"hardware_calls": len(hardware_calls)}}

    queue.enqueue(
        "session-software-only",
        {
            "software_only": True,
            "convert_to_h5": True,
            "cleaning": {"enabled": True, "angle_threshold": 2.0},
            "output": {"path": "/tmp/software-only.dat"},
        },
    )
    assert queue.start("session-software-only", executor) is True
    _wait_until(lambda: not queue.snapshot("session-software-only")["running"])

    job = queue.snapshot("session-software-only")["jobs"][0]
    assert job["status"] == "completed"
    assert job["result"] == {"hardware_calls": 0}
    assert hardware_calls == []
