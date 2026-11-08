"""Response authentication must precede definitive-rejection classification."""
import importlib
import io
import sys
from email.message import Message
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
transport = importlib.import_module("elyse_acq_transport")


class Response(io.BytesIO):
    def __init__(self, body, status, signatures):
        super().__init__(body)
        self.code = status
        self.headers = Message()
        for signature in signatures:
            self.headers.add_header("X-ACQ-Signature", signature)


class Replies:
    def __init__(self, port, status=200, value=None, signature="valid", raw=None):
        self.port, self.status, self.signature = port, status, signature
        self.raw = raw if raw is not None else transport.json_bytes(dict(
            schema_version=1, execution_allowed=False, hardware_writes=False,
            physical_status="NOT_EXECUTED", **(value or {"result": {}})))

    def open(self, request, timeout):
        nonce = request.get_header("X-acq-nonce")
        mac = transport.response_mac(self.port.key, request.method, "/v1/state", nonce, self.status, self.raw)
        signatures = {"valid": [mac], "missing": [], "bad": ["0" * 64], "duplicate": [mac, mac],
                      "tampered": [transport.response_mac(self.port.key, request.method, "/v1/state", nonce,
                                                          self.status, self.raw + b" ")]}
        return Response(self.raw, self.status, signatures[self.signature])


@pytest.fixture
def port():
    return transport.HttpAcqPort("http://10.20.30.10:8768", b"software-test-key-at-least-32-bytes")


@pytest.mark.parametrize("signature", ["missing", "bad", "duplicate", "tampered"])
def test_forged_definite_rejection_cannot_authorize_retry(port, signature):
    port._opener = Replies(port, status=409, value=dict(error="Rejected", accepted=False), signature=signature)
    with pytest.raises(ConnectionError, match="authentication failed"):
        port.read_state()


@pytest.mark.parametrize("status,value,expected", [
    (409, dict(error="Atomic conflict", accepted=False), transport.AcqRejected),
    (409, dict(error="Ambiguous conflict"), ConnectionError),
    (503, dict(error="Unknown dispatch", accepted=False), ConnectionError),
    (400, dict(error="Malformed request", accepted=False), ConnectionError),
])
def test_only_authenticated_409_nonacceptance_is_definitive(port, status, value, expected):
    port._opener = Replies(port, status=status, value=value)
    with pytest.raises(expected):
        port.read_state()


@pytest.mark.parametrize("changed", [dict(execution_allowed=True), dict(hardware_writes=True),
                                     dict(physical_status="SAFE"), dict(schema_version=2)])
def test_authenticated_hardware_contract_does_not_enable_output(port, changed):
    value = dict(result={}, **changed)
    # Replace authority fields in the canonical response after constructing it.
    response = dict(schema_version=1, execution_allowed=False, hardware_writes=False,
                    physical_status="NOT_EXECUTED", **{"result": {}})
    response.update(value)
    port._opener = Replies(port, raw=transport.json_bytes(response))
    with pytest.raises(ValueError, match="contract incompatible"):
        port.read_state()


def test_bounded_response_and_redirect_policy(port):
    port._opener = Replies(port, raw=b"x" * (transport.MAX_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds 65536"):
        port.read_state()
    with pytest.raises(ConnectionError, match="redirects are forbidden"):
        transport.NoRedirect().redirect_request(None, None, 302, "", {}, "http://example.com/")


def test_explicit_port_must_be_nonzero(port):
    with pytest.raises(ValueError):
        transport.HttpAcqPort("http://10.20.30.10:0", port.key)


@pytest.mark.parametrize("fault", ["signature", "id", "body", "unsigned", "status"])
def test_tcp_forged_rejection_remains_ambiguous(port, fault):
    tcp = transport.TcpAcqPort("tcp://10.20.30.10:8765", port.key)

    def exchange(request):
        params = request["params"]
        body = dict(schema_version=1, execution_allowed=False, hardware_writes=False,
                    physical_status="NOT_EXECUTED", accepted=False, error="Rejected")
        signature = transport.response_mac(tcp.key, "RPC/" + params["method"], params["path"],
                                           params["nonce"], 409, transport.json_bytes(body))
        reply = dict(id=request["id"], ok=True, result=dict(status=409, body=body, signature=signature))
        if fault == "signature":
            reply["result"]["signature"] = "0" * 64
        elif fault == "id":
            reply["id"] = "unrelated"
        elif fault == "body":
            reply["result"]["body"]["error"] = "Tampered"
        elif fault == "unsigned":
            reply["result"].pop("signature")
        else:
            reply["result"]["status"] = True
        return reply

    tcp._exchange = exchange
    with pytest.raises(ConnectionError):
        tcp.read_state()


def test_loopback_requires_explicit_local_simulation_opt_in(monkeypatch, port):
    monkeypatch.delenv("ELYSE_ACQ_LOCAL_SIMULATION", raising=False)
    config = dict(ELYSE_ACQ_URL="tcp://127.0.0.1:8765", ELYSE_ACQ_SHARED_KEY=port.key.decode())
    with pytest.raises(ValueError):
        transport.configured_acq(config)
    config["ELYSE_ACQ_LOCAL_SIMULATION"] = True
    assert isinstance(transport.configured_acq(config), transport.TcpAcqPort)
    assert transport.configured_acq(config).endpoint == "tcp://127.0.0.1:8765"
