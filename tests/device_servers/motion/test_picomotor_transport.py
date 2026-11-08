from collections import deque
from threading import Event, Thread

import pytest
from DeviceServers.motion.picomotor import (
    Picomotor8742,
    PicomotorDeviceError,
    PicomotorProtocolError,
    PicomotorTransportError,
    transport,
)

IDENTIFICATION = b"New_Focus 8742 v1.9 10/23/12 SN10001\r\n"


class FakeSocket:
    def __init__(self, script, startup=()):
        self.script = deque(script)
        self.incoming = deque(startup)
        self.sent = []
        self.timeouts = []
        self.closed = False
        self.on_recv = None

    def settimeout(self, value):
        self.timeouts.append(value)

    def sendall(self, payload):
        self.sent.append(payload)
        if payload.startswith(b"\xff"):
            return
        expected, response = self.script.popleft()
        assert payload == expected
        if isinstance(response, Exception):
            raise response
        if isinstance(response, bytes):
            self.incoming.append(response)
        elif response is not None:
            self.incoming.extend(response)

    def recv(self, size):
        if self.on_recv:
            self.on_recv()
        if not self.incoming:
            raise TimeoutError("fake socket has no response")
        data = self.incoming.popleft()
        if isinstance(data, Exception):
            raise data
        if len(data) > size:
            self.incoming.appendleft(data[size:])
        return data[:size]

    def close(self):
        self.closed = True


def make_controller(script=(), *, startup=(), address=0, identification=None):
    prefix = f"{address}>".encode() if address else b""
    if identification is None:
        identification = prefix + IDENTIFICATION
    fake = FakeSocket([(prefix + b"*IDN?\r", identification), *script], startup)
    calls = []

    def factory(endpoint, *, timeout):
        calls.append((endpoint, timeout))
        return fake

    controller = Picomotor8742(
        "192.0.2.10", controller_address=address, connection_factory=factory
    )
    return controller, fake, calls


def test_constructor_no_io_connect_readonly_idempotent_and_close_no_command():
    controller, fake, calls = make_controller()
    assert not controller.connected
    assert calls == fake.sent == []
    assert controller.connect() == IDENTIFICATION[:-2].decode()
    assert controller.connect() == IDENTIFICATION[:-2].decode()
    assert controller.connected
    assert len(calls) == 1 and calls[0][0] == ("192.0.2.10", 23)
    assert 0 < calls[0][1] <= 2
    controller.close()
    controller.close()
    assert fake.closed and not controller.connected
    assert fake.sent == [b"*IDN?\r"]


@pytest.mark.parametrize(
    "reply",
    [b"New_Focus 8743 v1.9 SN8742\r\n", b"unknown 8742\r\n", b"\r\n"],
)
def test_connect_rejects_other_models_or_malformed_identity(reply):
    controller, fake, _ = make_controller(identification=reply)
    with pytest.raises(PicomotorProtocolError):
        controller.connect()
    assert fake.closed and not controller.connected
    assert fake.sent == [b"*IDN?\r"]


def test_partial_telnet_options_and_subnegotiation_do_not_corrupt_identification():
    startup = [
        b"\xff",
        b"\xfb",
        b"\x01\xff\xfd",
        b"\x03",  # WILL ECHO / DO SGA
        b"\xff\xfc\x01\xff\xfe\x03",  # negative replies need no response
        b"\xff\xfa\x18abc\xff",
        b"\xffdef\xff",
        b"\xf0",  # SB...IAC SE
    ]
    controller, fake, _ = make_controller(
        startup=startup,
        identification=[IDENTIFICATION[:7], IDENTIFICATION[7:-1], b"\n"],
    )
    assert controller.connect() == IDENTIFICATION[:-2].decode()
    assert fake.sent == [b"\xff\xfe\x01", b"\xff\xfc\x03", b"*IDN?\r"]
    assert controller.connected


@pytest.mark.parametrize("startup", [[b"\xff", TimeoutError()], [b"abcdef"], [b""]])
def test_unknown_or_incomplete_startup_fails_before_identification(startup):
    controller, fake, _ = make_controller(startup=startup)
    with pytest.raises((PicomotorProtocolError, PicomotorTransportError)):
        controller.connect()
    assert fake.closed and not controller.connected
    assert fake.sent == []


def test_fragmented_crlf_position_done_and_error_queries():
    controller, fake, _ = make_controller(
        [
            (b"1TP?\r", [b"-214", b"7483648\r", b"\n"]),
            (b"2MD?\r", b"0\r\n"),
            (b"3MD?\r", b"1\r\n"),
            (b"TE?\r", b"107\r\n"),
        ]
    )
    controller.connect()
    assert controller.position(1) == -(2**31)
    assert controller.motion_done(2) is False
    assert controller.motion_done(3) is True
    assert controller.error_code() == 107
    assert controller.connected and not fake.script


@pytest.mark.parametrize("reply", [b"2\r\n", b"+1\r\n", b"1.0\r\n"])
def test_motion_done_requires_zero_or_one_and_closes_session(reply):
    controller, fake, _ = make_controller([(b"1MD?\r", reply)])
    controller.connect()
    with pytest.raises(PicomotorProtocolError):
        controller.motion_done(1)
    assert fake.closed and not controller.connected


@pytest.mark.parametrize("reply", [b"1.0\r\n", b"2147483648\r\n", b"NaN\r\n"])
def test_position_requires_signed_32_bit_integer(reply):
    controller, fake, _ = make_controller([(b"1TP?\r", reply)])
    controller.connect()
    with pytest.raises(PicomotorProtocolError):
        controller.position(1)
    assert fake.closed


def test_motion_and_origin_commands_check_one_error_without_retries():
    controller, fake, _ = make_controller(
        [
            (b"1PR-12\r", None),
            (b"TE?\r", b"0\r\n"),
            (b"2PA2147483647\r", None),
            (b"TE?\r", b"0\r\n"),
            (b"3DH-2147483648\r", None),
            (b"TE?\r", b"0\r\n"),
            (b"4ST\r", None),
            (b"TE?\r", b"0\r\n"),
            (b"AB\r", None),
            (b"TE?\r", b"0\r\n"),
        ]
    )
    controller.connect()
    controller.move_relative(1, -12)
    controller.move_absolute(2, 2**31 - 1)
    controller.define_position(3, -(2**31))
    controller.stop(4)
    controller.abort()
    assert len(fake.sent) == 11 and not fake.script


def test_nonzero_controller_error_surfaces_code_and_keeps_aligned_session():
    controller, fake, _ = make_controller(
        [(b"1PR10\r", None), (b"TE?\r", b"108\r\n"), (b"TE?\r", b"0\r\n")]
    )
    controller.connect()
    with pytest.raises(PicomotorDeviceError) as error:
        controller.move_relative(1, 10)
    assert error.value.code == 108 and error.value.command == "1PR10"
    assert controller.connected
    assert fake.sent == [b"*IDN?\r", b"1PR10\r", b"TE?\r"]
    assert controller.error_code() == 0  # Explicit subsequent read, never a drain.


@pytest.mark.parametrize("axis", [0, 5, True, 1.0, "1"])
def test_invalid_axes_cause_no_io(axis):
    controller, fake, _ = make_controller()
    controller.connect()
    for action in (
        lambda: controller.position(axis),
        lambda: controller.motion_done(axis),
        lambda: controller.stop(axis),
        lambda: controller.move_relative(axis, 1),
        lambda: controller.move_absolute(axis, 1),
        lambda: controller.define_position(axis, 1),
    ):
        with pytest.raises(ValueError):
            action()
    assert fake.sent == [b"*IDN?\r"] and controller.connected


@pytest.mark.parametrize("steps", [-(2**31) - 1, 2**31, True, 1.0, "1\rAB"])
def test_invalid_steps_cause_no_io(steps):
    controller, fake, _ = make_controller()
    controller.connect()
    for action in (
        controller.move_relative,
        controller.move_absolute,
        controller.define_position,
    ):
        with pytest.raises(ValueError):
            action(1, steps)
    assert fake.sent == [b"*IDN?\r"]


@pytest.mark.parametrize(
    "options",
    [
        {"host": ""},
        {"port": 0},
        {"port": True},
        {"timeout_s": 0},
        {"timeout_s": float("inf")},
        {"timeout_s": float("nan")},
        {"controller_address": -1},
        {"controller_address": 32},
        {"controller_address": True},
        {"connection_factory": 3},
    ],
)
def test_invalid_connection_options_rejected_before_network(options):
    arguments = {"host": "192.0.2.10", **options}
    with pytest.raises(ValueError):
        Picomotor8742(**arguments)


def test_slave_prefix_is_applied_and_required_for_queries_and_error_checks():
    controller, fake, _ = make_controller(
        [
            (b"3>2MD?\r", b"3>1\r\n"),
            (b"3>4TP?\r", b"3>-22\r\n"),
            (b"3>1PR5\r", None),
            (b"3>TE?\r", b"3>0\r\n"),
        ],
        address=3,
    )
    controller.connect()
    assert controller.motion_done(2)
    assert controller.position(4) == -22
    controller.move_relative(1, 5)
    assert not fake.script


@pytest.mark.parametrize(
    "address,reply", [(3, b"4>1\r\n"), (3, b"1\r\n"), (0, b"3>1\r\n")]
)
def test_wrong_or_missing_reply_address_closes_session(address, reply):
    command = (f"{address}>" if address else "").encode() + b"1MD?\r"
    controller, fake, _ = make_controller([(command, reply)], address=address)
    controller.connect()
    with pytest.raises(PicomotorProtocolError):
        controller.motion_done(1)
    assert fake.closed


@pytest.mark.parametrize(
    "failure", [b"", TimeoutError("read timeout"), OSError("receive failure")]
)
def test_incomplete_or_failed_reply_closes_without_reconnect(failure):
    controller, fake, calls = make_controller(
        [(b"1PR5\r", None), (b"TE?\r", [failure])]
    )
    controller.connect()
    with pytest.raises(PicomotorTransportError):
        controller.move_relative(1, 5)
    assert not controller.connected and fake.closed
    with pytest.raises(PicomotorTransportError):
        controller.position(1)
    assert len(calls) == 1 and fake.sent == [b"*IDN?\r", b"1PR5\r", b"TE?\r"]


def test_send_failure_is_not_replayed():
    controller, fake, calls = make_controller([(b"2PA10\r", OSError("partial send"))])
    controller.connect()
    with pytest.raises(PicomotorTransportError):
        controller.move_absolute(2, 10)
    assert fake.sent == [b"*IDN?\r", b"2PA10\r"] and len(calls) == 1
    assert fake.closed


@pytest.mark.parametrize(
    "reply",
    [b"0" * 4097 + b"\r\n", b"1\r\n2\r\n", b"1\x00\r\n", b"\xff\xff\r\n", b"1\n"],
)
def test_oversized_unexpected_control_or_unframed_replies_fail_closed(reply):
    controller, fake, _ = make_controller([(b"1TP?\r", reply)])
    controller.connect()
    with pytest.raises((PicomotorProtocolError, PicomotorTransportError)):
        controller.position(1)
    assert fake.closed and not controller.connected


def test_telnet_only_input_is_byte_bounded():
    controller, fake, _ = make_controller([(b"1TP?\r", b"\xff\xfb\x01" * 3000)])
    controller.connect()
    with pytest.raises(PicomotorProtocolError, match="byte limit"):
        controller.position(1)
    assert fake.closed


def test_partial_progress_does_not_extend_absolute_transaction_deadline(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    controller, fake, _ = make_controller([(b"1TP?\r", [b"1", b"2", b"3", b"\r\n"])])
    controller.connect()
    controller._timeout_s = 1.0
    fake.on_recv = lambda: now.__setitem__(0, now[0] + 0.4)
    with pytest.raises(PicomotorTransportError):
        controller.position(1)
    assert now[0] == pytest.approx(1.2)
    assert fake.closed
    assert fake.timeouts[-3:] == pytest.approx([1, 0.6, 0.2])


def test_write_and_error_query_are_one_serialized_transaction():
    controller, fake, _ = make_controller(
        [(b"1PR5\r", None), (b"TE?\r", b"0\r\n"), (b"2TP?\r", b"22\r\n")]
    )
    controller.connect()
    held, release, started, finished = Event(), Event(), Event(), Event()
    actual_send = fake.sendall
    errors = []

    def send(payload):
        actual_send(payload)
        if payload == b"1PR5\r":
            held.set()
            assert release.wait(2)

    fake.sendall = send

    def move():
        try:
            controller.move_relative(1, 5)
        except Exception as exc:
            errors.append(exc)

    def query():
        started.set()
        try:
            assert controller.position(2) == 22
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    mover = Thread(target=move)
    reader = Thread(target=query)
    mover.start()
    try:
        assert held.wait(1)
        reader.start()
        assert started.wait(1)
        assert not finished.wait(0.05)
        assert fake.sent == [b"*IDN?\r", b"1PR5\r"]
    finally:
        release.set()
        mover.join(2)
        if reader.ident is not None:
            reader.join(2)
    assert not errors and not mover.is_alive() and not reader.is_alive()
    assert fake.sent == [b"*IDN?\r", b"1PR5\r", b"TE?\r", b"2TP?\r"]


def test_default_factory_is_resolved_at_connect_time_for_network_guard(monkeypatch):
    controller = Picomotor8742("192.0.2.10")
    calls = []

    def deny(*args, **kwargs):
        calls.append(args)
        raise OSError("network guard")

    monkeypatch.setattr(transport.socket, "create_connection", deny)
    with pytest.raises(PicomotorTransportError):
        controller.connect()
    assert len(calls) == 1 and not controller.connected
