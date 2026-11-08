"""Disposable code-pushed attribute source for HDB++ round-trip tests."""

from __future__ import annotations

from datetime import datetime, timezone

from tango import AttrWriteType, DevState
from tango.server import Device, attribute, command


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DS_HdbppProbe(Device):
    @attribute(dtype=int, access=AttrWriteType.READ_WRITE)
    def value(self):
        return self._value

    def write_value(self, value):
        self._set_value(int(value))

    @attribute(dtype=int, access=AttrWriteType.READ)
    def sequence(self):
        return self._sequence

    @attribute(dtype=str, access=AttrWriteType.READ)
    def last_changed_at_utc(self):
        return self._last_changed_at_utc

    def init_device(self):
        Device.init_device(self)
        self._value = 0
        self._sequence = 0
        self._last_changed_at_utc = utc_now_iso()
        for name in ("value", "sequence", "last_changed_at_utc"):
            self.set_change_event(name, True, False)
            self.set_archive_event(name, True, False)
        self.set_state(DevState.ON)
        self.set_status("Disposable HDB++ acceptance probe; no hardware attached")

    def _push(self, name, value):
        self.push_change_event(name, value)
        self.push_archive_event(name, value)

    def _set_value(self, value: int):
        self._value = value
        self._sequence += 1
        self._last_changed_at_utc = utc_now_iso()
        self._push("value", self._value)
        self._push("sequence", self._sequence)
        self._push("last_changed_at_utc", self._last_changed_at_utc)

    @command(dtype_out=int)
    def advance(self):
        self._set_value(self._value + 1)
        return self._value

    @command(dtype_in=int, dtype_out=int)
    def set_test_value(self, value):
        self._set_value(int(value))
        return self._value


if __name__ == "__main__":
    DS_HdbppProbe.run_server()

