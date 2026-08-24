"""Cross-platform outbound-network guard for the software-only pytest lane."""

from __future__ import annotations

import ipaddress
import errno
import socket


class NetworkAccessBlocked(OSError):
    """Raised when a software-only test attempts external network access."""


def _host_from_address(address) -> object:
    if isinstance(address, tuple) and address:
        return address[0]
    return address


def _normalized_host(host) -> str:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    normalized = str(host or "").strip().strip("[]").lower()
    if "%" in normalized:
        normalized = normalized.split("%", 1)[0]
    return normalized


def _resolution_is_local(host) -> bool:
    normalized = _normalized_host(host)
    if normalized == "":
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    return bool(mapped is not None and mapped.is_loopback)


def _address_is_loopback(address) -> bool:
    normalized = _normalized_host(_host_from_address(address))
    try:
        host = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    if host.is_loopback:
        return True
    mapped = getattr(host, "ipv4_mapped", None)
    return bool(mapped is not None and mapped.is_loopback)


def _blocked(operation: str, address) -> NetworkAccessBlocked:
    return NetworkAccessBlocked(
        errno.EPERM,
        f"Software-only pytest lane blocked {operation} to {address!r}",
    )


def install_network_guard(monkeypatch) -> None:
    """Block external DNS/TCP/UDP while preserving loopback and Unix sockets."""
    actual_getaddrinfo = socket.getaddrinfo
    actual_create_connection = socket.create_connection
    actual_connect = socket.socket.connect
    actual_connect_ex = socket.socket.connect_ex
    actual_bind = socket.socket.bind
    actual_sendto = socket.socket.sendto
    actual_gethostbyname = socket.gethostbyname
    actual_gethostbyname_ex = socket.gethostbyname_ex
    actual_sendmsg = getattr(socket.socket, "sendmsg", None)
    unix_family = getattr(socket, "AF_UNIX", None)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not _resolution_is_local(host):
            raise _blocked("DNS resolution", host)
        return actual_getaddrinfo(host, *args, **kwargs)

    def guarded_create_connection(address, *args, **kwargs):
        if not _address_is_loopback(address):
            raise _blocked("connection", address)
        return actual_create_connection(address, *args, **kwargs)

    def guarded_host_lookup(host):
        if not _resolution_is_local(host):
            raise _blocked("DNS resolution", host)
        return actual_gethostbyname(host)

    def guarded_host_lookup_ex(host):
        if not _resolution_is_local(host):
            raise _blocked("DNS resolution", host)
        return actual_gethostbyname_ex(host)

    def guarded_host_by_address(host):
        raise _blocked("reverse DNS resolution", host)

    def guarded_name_info(address, flags):
        raise _blocked("reverse DNS resolution", address)

    def guarded_connect(sock, address):
        if unix_family is not None and sock.family == unix_family:
            return actual_connect(sock, address)
        if not _address_is_loopback(address):
            raise _blocked("connection", address)
        return actual_connect(sock, address)

    def guarded_connect_ex(sock, address):
        if unix_family is not None and sock.family == unix_family:
            return actual_connect_ex(sock, address)
        if not _address_is_loopback(address):
            raise _blocked("connection", address)
        return actual_connect_ex(sock, address)

    def guarded_bind(sock, address):
        if unix_family is not None and sock.family == unix_family:
            return actual_bind(sock, address)
        if not _address_is_loopback(address):
            raise _blocked("bind", address)
        return actual_bind(sock, address)

    def guarded_sendto(sock, *args):
        address = args[-1] if args else None
        if unix_family is not None and sock.family == unix_family:
            return actual_sendto(sock, *args)
        if not _address_is_loopback(address):
            raise _blocked("datagram", address)
        return actual_sendto(sock, *args)

    def guarded_sendmsg(sock, *args):
        address = args[3] if len(args) >= 4 else None
        if address is None:
            return actual_sendmsg(sock, *args)
        if unix_family is not None and sock.family == unix_family:
            return actual_sendmsg(sock, *args)
        if not _address_is_loopback(address):
            raise _blocked("datagram", address)
        return actual_sendmsg(sock, *args)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(socket, "gethostbyname", guarded_host_lookup)
    monkeypatch.setattr(socket, "gethostbyname_ex", guarded_host_lookup_ex)
    monkeypatch.setattr(socket, "gethostbyaddr", guarded_host_by_address)
    monkeypatch.setattr(socket, "getnameinfo", guarded_name_info)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "bind", guarded_bind)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    if actual_sendmsg is not None:
        monkeypatch.setattr(socket.socket, "sendmsg", guarded_sendmsg)
