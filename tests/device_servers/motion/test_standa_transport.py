from threading import Event, Thread

import pytest
from DeviceServers.motion.standa.transport import (
    StandaTransportBusyError,
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
