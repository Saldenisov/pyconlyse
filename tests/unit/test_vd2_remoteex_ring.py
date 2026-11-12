"""RemoteEx Live ring framing and first-frame integrity."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from DeviceServers.cameras.hamamatsu_streak.remoteex_client import RemoteExClient
from DeviceServers.cameras.hamamatsu_streak.remoteex_protocol import RemoteExProtocolError, parse_response_line


def test_native_ring_timestamp_and_first_notification(monkeypatch):
    client = RemoteExClient()
    client._paired_monitor = True
    client._data_socket = object()
    client._command_socket = SimpleNamespace(sendall=lambda payload: None, settimeout=lambda value: None)
    messages = iter([
        "4,LiveMonitor,ringbuffer,93", "4,LiveMonitor,ringbuffer,94",
        "0,ImgRingBufferGet,2,1,2,0,93,70591.230",
    ])
    monkeypatch.setattr(client, "_read_line", lambda _: next(messages))
    monkeypatch.setattr(client, "connect", lambda **kwargs: None)
    monkeypatch.setattr(client, "_discard_pending_data", lambda: None)
    monkeypatch.setattr(client, "read_data_exact", lambda size: bytes(size))
    image = client.read_paired_image(-1)
    assert client.first_paired_sequence == image.sequence_number == 93
    assert image.timestamp_ms == pytest.approx(70591.230)
    monkeypatch.setattr(client, "get_ring_buffer_image", lambda *_: replace(image, sequence_number=94))
    with pytest.raises(RemoteExProtocolError, match="first frame"):
        client.read_paired_image(-1)


def test_absent_native_timestamp_stays_unavailable(monkeypatch):
    client = RemoteExClient()
    monkeypatch.setattr(client, "read_data_exact", lambda size: bytes(size))
    image = client._read_image_response(
        parse_response_line("0,ImgRingBufferGet,2,1,2,0,93"), "ImgRingBufferGet",
    )
    assert image.timestamp_ms is None
