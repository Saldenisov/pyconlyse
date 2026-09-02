from threading import Event, Thread

import pytest
from DeviceServers.motion.standa.transport import (
    StandaTransportBusyError,
    device_lock_path,
    exclusive_standa_transport,
)


def test_standa_transport_lock_serializes_competing_threads(tmp_path):
    lock_path = tmp_path / "standa-ximc.lock"
    acquired = Event()
    release = Event()

    def hold_transport():
        with exclusive_standa_transport(str(lock_path), timeout_seconds=1.0):
            acquired.set()
            release.wait(timeout=1.0)

    holder = Thread(target=hold_transport)
    holder.start()
    assert acquired.wait(timeout=1.0)

    with pytest.raises(StandaTransportBusyError):
        with exclusive_standa_transport(str(lock_path), timeout_seconds=0.05):
            pass

    release.set()
    holder.join(timeout=1.0)
    assert not holder.is_alive()


def test_standa_transport_lock_releases_after_scope(tmp_path):
    lock_path = tmp_path / "standa-ximc.lock"

    with exclusive_standa_transport(str(lock_path), timeout_seconds=0.1):
        pass
    with exclusive_standa_transport(str(lock_path), timeout_seconds=0.1):
        pass


def test_device_lock_path_is_stable_and_controller_specific(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "PYCONLYSE_STANDA_TRANSPORT_LOCK", str(tmp_path / "standa-ximc.lock")
    )

    first = device_lock_path("15731")
    second = device_lock_path("15722")

    assert first == tmp_path / "standa-ximc-15731.lock"
    assert second == tmp_path / "standa-ximc-15722.lock"
    assert first != second
