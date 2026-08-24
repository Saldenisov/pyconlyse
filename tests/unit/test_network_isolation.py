import os
import socket

import pytest

from scripts.refactor.pytest_network_guard import (
    NetworkAccessBlocked,
    _address_is_loopback,
    _resolution_is_local,
    install_network_guard,
)


def test_network_guard_classifies_only_loopback_as_connectable():
    assert _address_is_loopback(("127.0.0.1", 8080)) is True
    assert _address_is_loopback(("::1", 8080)) is True
    assert _address_is_loopback(("localhost", 8080)) is False
    assert _address_is_loopback(("::ffff:127.0.0.1", 8080)) is True
    assert _address_is_loopback(("::1%lo0", 8080)) is True
    assert _address_is_loopback(("192.0.2.10", 8080)) is False
    assert _address_is_loopback(("everest", 10000)) is False


def test_network_guard_allows_numeric_resolution_without_external_dns():
    assert _resolution_is_local("127.0.0.1") is True
    assert _resolution_is_local(b"::1") is True
    assert _resolution_is_local("0.0.0.0") is False
    assert _resolution_is_local("localhost") is False
    assert _resolution_is_local("example.com") is False


def test_network_guard_activation_matches_gate_mode():
    if os.environ.get("PYCONLYSE_DENY_NETWORK") == "1":
        assert os.environ.get("PYCONLYSE_NETWORK_GUARD_ACTIVE") == "1"
        assert socket.socket.connect.__module__ == "scripts.refactor.pytest_network_guard"
    else:
        assert os.environ.get("PYCONLYSE_NETWORK_GUARD_ACTIVE") is None
        assert getattr(socket.socket.connect, "__module__", None) != (
            "scripts.refactor.pytest_network_guard"
        )


def test_network_guard_blocks_external_dns_and_connect_before_system_calls(
    monkeypatch,
):
    install_network_guard(monkeypatch)

    with pytest.raises(NetworkAccessBlocked, match="DNS resolution"):
        socket.getaddrinfo("example.com", 443)

    with pytest.raises(NetworkAccessBlocked, match="DNS resolution"):
        socket.getaddrinfo("localhost", 443)

    with pytest.raises(NetworkAccessBlocked, match="connection"):
        socket.create_connection(("192.0.2.10", 443))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkAccessBlocked, match="connection"):
            sock.connect(("192.0.2.10", 443))
        with pytest.raises(NetworkAccessBlocked, match="connection"):
            sock.connect_ex(("192.0.2.10", 443))
        with pytest.raises(NetworkAccessBlocked, match="bind"):
            sock.bind(("0.0.0.0", 0))
    finally:
        sock.close()

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(NetworkAccessBlocked, match="datagram"):
            udp.sendto(b"blocked", ("192.0.2.10", 9))
    finally:
        udp.close()


def test_network_guard_allows_literal_loopback_tcp(monkeypatch):
    install_network_guard(monkeypatch)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    client = socket.create_connection(listener.getsockname(), timeout=1.0)
    accepted, _address = listener.accept()
    accepted.close()
    client.close()
    listener.close()


def test_network_guard_restores_exact_socket_functions():
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    with pytest.MonkeyPatch.context() as guard:
        install_network_guard(guard)
        assert socket.socket.connect is not original_connect
        assert socket.getaddrinfo is not original_getaddrinfo

    assert socket.socket.connect is original_connect
    assert socket.getaddrinfo is original_getaddrinfo
