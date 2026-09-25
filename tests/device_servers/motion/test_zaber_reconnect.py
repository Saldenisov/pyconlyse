"""The disconnected Zaber server stays alive and reconnects without motion."""

import threading

from DeviceServers.motion.zaber.reconnect import ZaberConnectionMonitor


class FakeStage:
    def __init__(self):
        self.powered = False
        self.connected = False
        self.connect_calls = 0
        self.snapshot_calls = 0
        self.close_calls = 0

    def connect(self):
        self.connect_calls += 1
        if not self.powered:
            raise OSError("controller power is off")
        self.connected = True
        return "ready"

    def snapshot(self):
        self.snapshot_calls += 1
        if not self.powered:
            raise OSError("controller power was lost")
        return "ready"

    def close(self):
        self.close_calls += 1
        self.connected = False


def test_retries_after_power_arrives_and_detects_later_power_loss():
    stage = FakeStage()
    ready = threading.Event()
    snapshots = []
    errors = []
    monitor = ZaberConnectionMonitor(
        stage, threading.RLock(), lambda: False,
        lambda snapshot: (snapshots.append(snapshot), ready.set()),
        errors.append,
        interval_s=0.1,
    )
    monitor.probe_once()
    assert stage.connect_calls == 1
    assert errors and not stage.connected

    monitor.start()
    try:
        stage.powered = True
        assert ready.wait(0.6)
        assert stage.connected
        assert snapshots[0] == "ready"
        stage.powered = False
        monitor.probe_once()
        assert not stage.connected
        assert stage.close_calls >= 2
    finally:
        assert monitor.stop()


def test_does_not_probe_serial_port_while_stage_moves():
    stage = FakeStage()
    monitor = ZaberConnectionMonitor(
        stage, threading.RLock(), lambda: True,
        lambda _: None, lambda _: None,
    )
    monitor.probe_once()
    assert stage.connect_calls == 0
