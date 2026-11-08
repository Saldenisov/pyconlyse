import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
import vd2_live_acquisition as live


def test_sequence_wait_yields_between_status_reads_for_preview(monkeypatch):
    calls = []
    replies = iter(["0,AsyncCommandStatus,1,0,1,SeqStart()",
                    "0,AsyncCommandStatus,1,0,1,SeqStart()",
                    "0,AsyncCommandStatus,0,0,0,"])

    class Proxy:
        def command_inout(self, command, value):
            calls.append((command, value))
            return next(replies)

    monkeypatch.setattr(live.time, "sleep", lambda _: calls.append("preview can run"))
    live.wait_for_sequence(Proxy())
    assert calls == [("ExecuteRaw", "AsyncCommandStatus()"), "preview can run",
                     ("ExecuteRaw", "AsyncCommandStatus()"), "preview can run",
                     ("ExecuteRaw", "AsyncCommandStatus()")]


@pytest.mark.parametrize("reply", ["", "0,Wrong,0,0,0", "0,AsyncCommandStatus,0",
                                  "0,AsyncCommandStatus,0,2,0", "3,AsyncCommandStatus,0,0,0"])
def test_unverified_status_fails_without_replaying_acquisition(reply):
    calls = []
    class Proxy:
        def command_inout(self, command, value):
            calls.append((command, value))
            return reply
    with pytest.raises(RuntimeError, match="Invalid sequence status"):
        live.wait_for_sequence(Proxy())
    assert calls == [("ExecuteRaw", "AsyncCommandStatus()")]


def test_timeout_does_not_issue_stop_or_restart(monkeypatch):
    times = iter([0, 0.1, 0.2, 2.0])
    monkeypatch.setattr(live.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(live.time, "sleep", lambda _: None)
    calls = []
    class Proxy:
        def command_inout(self, command, value):
            calls.append((command, value))
            return "0,AsyncCommandStatus,1,0,1,SeqStart()"
    with pytest.raises(TimeoutError, match="acquisition not replayed"):
        live.wait_for_sequence(Proxy(), timeout_s=1)
    assert calls == [("ExecuteRaw", "AsyncCommandStatus()")] * 2
