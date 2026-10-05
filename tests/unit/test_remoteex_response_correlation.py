"""Packet-level reply correlation without sockets or hardware."""

import pytest

from DeviceServers.cameras.hamamatsu_streak.remoteex_client import RemoteExClient
from DeviceServers.cameras.hamamatsu_streak.remoteex_protocol import RemoteExTransportError


class PacketSocket:
    def __init__(self, payload):
        self.payload = bytearray(payload)
        self.sent = []
        self.timeouts = []

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, count):
        if not self.payload:
            raise TimeoutError("no matching response")
        data = bytes(self.payload[:count])
        del self.payload[:count]
        return data


def client_with_packets(payload):
    client = RemoteExClient()
    sock = PacketSocket(payload)
    client._command_socket = sock
    return client, sock


def test_appinfo_does_not_accept_a_late_appstart_or_parameter_reply():
    client, sock = client_with_packets(b"0,AppStart\r0,DevParamGet,Closed\r0,AppInfo,9.5\r")
    response = client.send_command_checked("AppInfo(Version)")
    assert response.command_name == "AppInfo"
    assert response.parameter(0) == "9.5"
    assert sock.sent == [b"AppInfo(Version)\r"]
    assert [m.command_name for m in client.last_messages] == ["AppStart", "DevParamGet"]


def test_status_boundary_realigns_parameter_stream():
    client, sock = client_with_packets(b"0,DevParamGet,Full speed\r0,Status,0,\r0,DevParamGet,800\r")
    assert client.send_command_checked("Status()").parameter(0) == "0"
    assert client.send_command_checked("DevParamGet(Spec,Blaze)").parameter(0) == "800"
    assert len(sock.sent) == 2


def test_wrong_reply_never_acknowledges_a_shutter_write_or_replays_it():
    client, sock = client_with_packets(b"0,DevParamGet,Closed\r")
    with pytest.raises(RemoteExTransportError):
        client.send_command_checked("DevParamSet(Spec,Shutter,Open)", timeout=30.0)
    assert sock.sent == [b"DevParamSet(Spec,Shutter,Open)\r"]
    assert client.last_response is None


def test_unrelated_stream_is_bounded():
    client, sock = client_with_packets(b"0,DevParamGet,Closed\r" * 16)
    with pytest.raises(RemoteExTransportError, match="Too many unrelated replies"):
        client.send_command_checked("Status()")
    assert len(sock.sent) == 1
