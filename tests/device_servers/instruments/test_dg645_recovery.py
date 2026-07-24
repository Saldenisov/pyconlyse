import sys
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from DeviceServers.instruments.dg645.DS_DG645 import DS_DG645


class FailingSession:
    def __init__(self):
        self.closed = False
        self.calls = []

    def query(self, command):
        self.calls.append(command)
        raise OSError("stale socket")

    def write(self, command):
        self.calls.append(command)
        raise OSError("stale socket")

    def close(self):
        self.closed = True


class WorkingSession:
    def __init__(self, response="Stanford Research Systems,DG645,123,1.0"):
        self.response = response
        self.calls = []
        self.closed = False

    def query(self, command):
        self.calls.append(command)
        return self.response

    def write(self, command):
        self.calls.append(command)

    def close(self):
        self.closed = True


def test_find_device_falls_back_after_driver_session_fails_identity_query():
    failed = FailingSession()
    working = WorkingSession()
    closed = []
    device = SimpleNamespace(
        driver_backend="auto",
        _session=None,
        _rm=None,
        _active_backend="",
        _device_id_internal=-1,
        _uri="",
        _idn_cache="",
    )
    device._open_srsinst_session = lambda: (failed, "tcpip://10.20.30.131:5025")
    device._open_scpi_session = lambda: (working, "tcp://10.20.30.131:5025")
    device._close_session = lambda: (
        closed.append(device._session),
        setattr(device, "_session", None),
        setattr(device, "_active_backend", ""),
    )
    device.set_state = lambda state: setattr(device, "state", state)
    device.info = lambda *args, **kwargs: None
    device.error = lambda *args, **kwargs: None

    DS_DG645.find_device(device)

    assert failed in closed
    assert device._session is working
    assert device._active_backend == "raw-scpi"
    assert device._device_id_internal == 1
    assert device._idn_cache.startswith("Stanford Research Systems")


def test_query_reconnects_once_after_stale_transport_failure():
    failed = FailingSession()
    working = WorkingSession("DG645 OK")
    device = SimpleNamespace(_session=failed, _rm=None, _active_backend="srsinst.dg645")
    device._ensure_session = lambda: None
    device.warn = lambda *args, **kwargs: None
    device._close_session = lambda: setattr(device, "_session", None)
    device.find_device = lambda: setattr(device, "_session", working)

    response = DS_DG645._execute_with_reconnect(device, "query", "*IDN?")

    assert response == "DG645 OK"
    assert failed.calls == ["*IDN?"]
    assert working.calls == ["*IDN?"]


def test_non_idempotent_write_reconnects_without_replaying_command():
    failed = FailingSession()
    working = WorkingSession()
    device = SimpleNamespace(_session=failed, _rm=None, _active_backend="srsinst.dg645")
    device._ensure_session = lambda: None
    device.warn = lambda *args, **kwargs: None
    device._close_session = lambda: setattr(device, "_session", None)
    device.find_device = lambda: setattr(device, "_session", working)

    try:
        DS_DG645._execute_with_reconnect(device, "write", "*TRG", retry=False)
    except RuntimeError as exc:
        assert "was not replayed" in str(exc)
    else:
        raise AssertionError("Expected non-idempotent write to avoid replay")

    assert failed.calls == ["*TRG"]
    assert working.calls == []
