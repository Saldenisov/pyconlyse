"""T11 executable contract for the pure hardware authorization gate.

These tests use only temporary policy/approval directories and fake operations.
They must never create a Tango proxy or expose approval-generation behavior.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import sys
import threading
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
os.environ.setdefault("TANGO_HOST", "stub.invalid:1")
os.environ.setdefault("PYCONLYSE_TANGO_HOST", "stub.invalid:1")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

import hardware_authorization
from tests.web._hardware_authorization_test_support import (
    simulate_hardware_authorization_service_acl,
)
from hardware_authorization import (
    AuthorizationConfig,
    AuthorizationError,
    Operation,
    authorize_operation,
    consume_approval,
    load_policy,
)


NONCE = "a" * 64


def operation(**overrides):
    values = {
        "method": "POST",
        "route_id": "device.command",
        "action": "execute",
        "targets": ({"device": "motor/test", "command": "move_axis"},),
        "args": {"axis": 1, "position": 2.5},
    }
    values.update(overrides)
    return Operation(**values)


def write_contract(tmp_path, *, policy=None, approval=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    policy_path = tmp_path / "policy.json"
    approval_dir = tmp_path / "approvals"
    consumed_dir = tmp_path / "consumed"
    approval_dir.mkdir()
    consumed_dir.mkdir()
    policy_path.write_text(json.dumps(policy or {
        "version": 1,
        "subjects": {"alice": {"roles": ["operator"]}, "bob": {"roles": ["operator"]}},
        "roles": {"operator": {"device.command": ["execute"]}},
        "operations": [{
            "method": "POST",
            "route_id": "device.command",
            "action": "execute",
            "targets": [{"device": "motor/test", "command": "move_axis"}],
            "roles": ["operator"],
            "args": {
                "type": "object",
                "required": ["axis", "position"],
                "additionalProperties": False,
                "properties": {
                    "axis": {"type": "integer", "minimum": 0, "maximum": 15},
                    "position": {"type": "number", "minimum": -1000, "maximum": 1000},
                },
            },
        }],
    }), encoding="utf-8")
    if approval is not None:
        (approval_dir / f"{approval['nonce']}.json").write_text(
            json.dumps(approval), encoding="utf-8"
        )
    config = AuthorizationConfig(
        policy_path=policy_path,
        approval_dir=approval_dir,
        consumed_dir=consumed_dir,
        strict=True,
    )
    return config


def approval(op=None, *, subject="alice", role="operator", nonce=NONCE,
             expires_at=None):
    op = op or operation()
    issued_at = datetime.now(timezone.utc)
    return {
        "version": 1,
        "subject": subject,
        "role": role,
        "method": op.method,
        "route_id": op.route_id,
        "action": op.action,
        "targets": list(op.targets),
        "args": op.args,
        "approved_by": "Operator One",
        "hardware_safe": True,
        "nonce": nonce,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at or (issued_at + timedelta(minutes=5)).isoformat(),
    }


def test_valid_approval_binds_identity_operation_and_canonical_args(tmp_path):
    op = operation()
    config = write_contract(tmp_path, approval=approval(op))
    assert authorize_operation(config, subject="alice", role="operator", operation=op, nonce=NONCE)


@pytest.mark.parametrize("field", ["subject", "role", "route_id", "action", "targets", "args"])
def test_mismatched_approval_is_409(tmp_path, field):
    op = operation()
    data = approval(op)
    data[field] = "wrong" if field not in {"targets", "args"} else []
    config = write_contract(tmp_path, approval=data)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=op, nonce=NONCE)
    assert exc.value.status_code == 409


def test_missing_approval_is_428_and_policy_denial_is_403(tmp_path):
    config = write_contract(tmp_path)
    with pytest.raises(AuthorizationError) as missing:
        authorize_operation(config, subject="alice", role="operator", operation=operation(), nonce=NONCE)
    assert missing.value.status_code == 428

    denied = write_contract(tmp_path / "denied", policy={"roles": {}, "operations": []}, approval=approval())
    with pytest.raises(AuthorizationError) as forbidden:
        authorize_operation(denied, subject="alice", role="operator", operation=operation(), nonce=NONCE)
    assert forbidden.value.status_code == 403


def test_expired_nonce_and_replay_are_409(tmp_path):
    op = operation()
    expired = approval(op, expires_at="2000-01-01T00:00:00+00:00")
    config = write_contract(tmp_path, approval=expired)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=op, nonce=NONCE)
    assert exc.value.status_code == 409

    config = write_contract(tmp_path / "replay", approval=approval(op))
    assert consume_approval(config, NONCE) is True
    with pytest.raises(AuthorizationError) as replay:
        consume_approval(config, NONCE)
    assert replay.value.status_code == 409


def test_consumption_marker_exists_before_side_effect(tmp_path):
    op = operation()
    config = write_contract(tmp_path, approval=approval(op))
    observed = []

    def fake_proxy():
        observed.append((config.consumed_dir / f"{NONCE}.used").exists())

    authorize_operation(config, subject="alice", role="operator", operation=op,
                        nonce=NONCE, before_side_effect=fake_proxy)
    assert observed == [True]
    assert (config.consumed_dir / f"{NONCE}.used").exists()


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX directory-fsync contract; Windows has dedicated WinAPI durability tests",
)
def test_directory_fsync_failure_fails_closed_after_consuming_marker(
    monkeypatch, tmp_path
):
    config = write_contract(tmp_path, approval=approval())
    effects = []
    actual_fsync = os.fsync
    fsync_calls = []

    def fail_directory_fsync(descriptor):
        fsync_calls.append(descriptor)
        if len(fsync_calls) == 2:
            raise OSError("directory fsync failed")
        return actual_fsync(descriptor)

    monkeypatch.setattr(hardware_authorization.os, "fsync", fail_directory_fsync)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(
            config,
            subject="alice",
            role="operator",
            operation=operation(),
            nonce=NONCE,
            before_side_effect=lambda: effects.append(True),
        )

    assert exc.value.status_code == 409
    assert len(fsync_calls) == 2
    assert (config.consumed_dir / f"{NONCE}.used").exists()
    assert effects == []


def test_concurrent_consumption_has_exactly_one_success(tmp_path):
    config = write_contract(tmp_path, approval=approval())
    results = []

    def consume():
        try:
            results.append(consume_approval(config, NONCE))
        except AuthorizationError:
            results.append(False)

    threads = [threading.Thread(target=consume) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count(True) == 1


@pytest.mark.parametrize("bad", ["*", "motor/*"])
def test_wildcards_unknown_fields_and_nonfinite_values_rejected(tmp_path, bad):
    op = operation(targets=({"device": bad, "command": "move_axis"},))
    config = write_contract(tmp_path, approval=approval(op))
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=op, nonce=NONCE)
    assert exc.value.status_code == 409


def test_duplicate_json_keys_and_nonfinite_json_are_rejected(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"roles": {}, "roles": {}}', encoding="utf-8")
    with pytest.raises(AuthorizationError):
        load_policy(duplicate)

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value": NaN}', encoding="utf-8")
    with pytest.raises(AuthorizationError):
        load_policy(nonfinite)


def test_policy_unknown_key_is_403(tmp_path):
    policy = {
        "version": 1,
        "subjects": {"alice": ["operator"]},
        "roles": {"operator": {"device.command": ["execute"]}},
        "operations": [],
        "unexpected": True,
    }
    with pytest.raises(AuthorizationError) as exc:
        load_policy(write_contract(tmp_path, policy=policy).policy_path, strict=True)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("version", (True, 1.0))
def test_strict_policy_version_requires_exact_integer_one(tmp_path, version):
    config = write_contract(tmp_path, approval=None)
    policy = json.loads(config.policy_path.read_text(encoding="utf-8"))
    policy["version"] = version
    config.policy_path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(AuthorizationError) as exc:
        load_policy(config.policy_path, strict=True)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("field", ["version", "method", "approved_by", "hardware_safe", "issued_at"])
def test_approval_required_fields_are_strict_409(tmp_path, field):
    data = approval()
    data.pop(field)
    config = write_contract(tmp_path, approval=data)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=operation(), nonce=NONCE)
    assert exc.value.status_code == 409


def test_approval_unknown_key_is_409(tmp_path):
    data = approval()
    data["unexpected"] = True
    config = write_contract(tmp_path, approval=data)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=operation(), nonce=NONCE)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("version", (True, 1.0))
def test_strict_approval_version_requires_exact_integer_one(tmp_path, version):
    data = approval()
    data["version"] = version
    config = write_contract(tmp_path, approval=data)

    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(
            config, subject="alice", role="operator", operation=operation(), nonce=NONCE
        )
    assert exc.value.status_code == 409


def test_canonical_argument_key_order_is_equivalent(tmp_path):
    op = operation(args={"position": 2.5, "axis": 1})
    data = approval(operation(args={"axis": 1, "position": 2.5}))
    config = write_contract(tmp_path, approval=data)
    assert authorize_operation(config, subject="alice", role="operator", operation=op, nonce=NONCE)


def test_invalid_utc_offset_is_409(tmp_path):
    data = approval(expires_at="2026-01-01T00:00:00")
    config = write_contract(tmp_path, approval=data)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=operation(), nonce=NONCE)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("field", ["issued_at", "expires_at"])
def test_nonzero_utc_offset_is_409(tmp_path, field):
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=60)
    data = approval(expires_at=expires_at.isoformat())
    data["issued_at"] = issued_at.isoformat()
    offset = timezone(timedelta(hours=1))
    data[field] = (issued_at if field == "issued_at" else expires_at).astimezone(offset).isoformat()
    config = write_contract(tmp_path, approval=data)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=operation(), nonce=NONCE)
    assert exc.value.status_code == 409


class _FakeWindowsKernel32:
    def __init__(self, *, write_ok=True, flush_ok=True, close_ok=True):
        self.write_ok = write_ok
        self.flush_ok = flush_ok
        self.close_ok = close_ok
        self.last_error = 5
        self.created = set()
        self.calls = []

    def CreateFileW(self, path, desired_access, share_mode, security, creation, flags, template):
        self.calls.append(("create", path, desired_access, share_mode, creation, flags))
        if path in self.created:
            self.last_error = 80
            return -1
        Path(path).touch(exist_ok=False)
        self.created.add(path)
        return 101

    def WriteFile(self, handle, buffer, length, written, overlapped):
        self.calls.append(("write", handle, length))
        if not self.write_ok:
            self.last_error = 1117
            return False
        written._obj.value = length
        return True

    def FlushFileBuffers(self, handle):
        self.calls.append(("flush", handle))
        if not self.flush_ok:
            self.last_error = 112
        return self.flush_ok

    def CloseHandle(self, handle):
        self.calls.append(("close", handle))
        if not self.close_ok:
            self.last_error = 6
        return self.close_ok

    def GetLastError(self):
        return self.last_error


def _use_mocked_windows_consumption(monkeypatch, kernel32):
    monkeypatch.setattr(hardware_authorization, "_is_windows", lambda: True)
    monkeypatch.setattr(hardware_authorization, "_native_windows", lambda: False)
    monkeypatch.setattr(hardware_authorization, "_windows_kernel32", lambda: kernel32)


def test_windows_error_uses_ctypes_saved_error_on_native_windows(monkeypatch):
    kernel32 = _FakeWindowsKernel32()
    monkeypatch.setattr(hardware_authorization, "_native_windows", lambda: True)
    monkeypatch.setattr(hardware_authorization, "_ctypes_last_error", lambda: 1234)
    kernel32.GetLastError = lambda: pytest.fail("native path must not call GetLastError")

    assert hardware_authorization._windows_error(kernel32, "marker failure").errno == 1234


def test_windows_consumption_is_create_new_write_through_and_precedes_side_effect(monkeypatch, tmp_path):
    config = write_contract(tmp_path, approval=approval())
    kernel32 = _FakeWindowsKernel32()
    _use_mocked_windows_consumption(monkeypatch, kernel32)
    effects = []

    authorize_operation(
        config,
        subject="alice",
        role="operator",
        operation=operation(),
        nonce=NONCE,
        before_side_effect=lambda: effects.append(
            (config.consumed_dir / f"{NONCE}.used").exists()
        ),
    )

    assert [call[0] for call in kernel32.calls] == ["create", "write", "flush", "close"]
    create = kernel32.calls[0]
    assert create[3] == 0 and create[4] == 1
    assert create[5] & 0x80000000
    assert effects == [True]


def test_windows_consumption_replay_fails_closed(monkeypatch, tmp_path):
    config = write_contract(tmp_path, approval=approval())
    kernel32 = _FakeWindowsKernel32()
    _use_mocked_windows_consumption(monkeypatch, kernel32)
    assert consume_approval(config, NONCE) is True
    with pytest.raises(AuthorizationError) as exc:
        consume_approval(config, NONCE)
    assert exc.value.status_code == 409


@pytest.mark.parametrize(
    ("failure", "error_code"),
    [("write_ok", 1117), ("flush_ok", 112)],
)
def test_windows_marker_write_or_flush_failure_fails_closed(
    monkeypatch, tmp_path, failure, error_code
):
    config = write_contract(tmp_path, approval=approval())
    kernel32 = _FakeWindowsKernel32(**{failure: False})
    _use_mocked_windows_consumption(monkeypatch, kernel32)
    effects = []
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(
            config,
            subject="alice",
            role="operator",
            operation=operation(),
            nonce=NONCE,
            before_side_effect=lambda: effects.append(True),
        )
    assert exc.value.status_code == 409
    assert exc.value.__cause__.errno == error_code
    assert [call[0] for call in kernel32.calls][-1] == "close"
    assert (config.consumed_dir / f"{NONCE}.used").exists()
    assert effects == []


def test_windows_close_failure_fails_closed_after_marker_creation(monkeypatch, tmp_path):
    config = write_contract(tmp_path, approval=approval())
    kernel32 = _FakeWindowsKernel32(close_ok=False)
    _use_mocked_windows_consumption(monkeypatch, kernel32)
    with pytest.raises(AuthorizationError) as exc:
        consume_approval(config, NONCE)
    assert exc.value.status_code == 409
    assert [call[0] for call in kernel32.calls] == ["create", "write", "flush", "close"]


def test_environment_config_requires_absolute_external_directories(monkeypatch, tmp_path):
    config_root = tmp_path / "external"
    config = write_contract(config_root, approval=None)
    monkeypatch.setenv("PYCONLYSE_HARDWARE_POLICY_PATH", str(config.policy_path))
    monkeypatch.setenv("PYCONLYSE_HARDWARE_APPROVAL_DIR", str(config.approval_dir))
    monkeypatch.setenv("PYCONLYSE_HARDWARE_CONSUMED_DIR", str(config.consumed_dir))
    from hardware_authorization import authorization_config_from_environment

    config = authorization_config_from_environment()
    assert config.policy_path.is_absolute()
    assert config.approval_dir.is_absolute()
    assert config.consumed_dir.is_absolute()


def test_service_acl_simulation_keeps_authorization_inputs_readonly(
    monkeypatch, tmp_path
):
    config = write_contract(tmp_path / "external", approval=approval())
    environ = {
        "PYCONLYSE_HARDWARE_POLICY_PATH": str(config.policy_path),
        "PYCONLYSE_HARDWARE_APPROVAL_DIR": str(config.approval_dir),
        "PYCONLYSE_HARDWARE_CONSUMED_DIR": str(config.consumed_dir),
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "true",
        "PYCONLYSE_PRODUCTION": "false",
    }
    simulate_hardware_authorization_service_acl(
        monkeypatch,
        policy_path=config.policy_path,
        approval_dir=config.approval_dir,
        consumed_dir=config.consumed_dir,
    )

    strict_config = hardware_authorization.authorization_config_from_environment(
        environ
    )

    assert strict_config.require_readonly_approvals is True


@pytest.mark.parametrize(
    ("untrusted_path", "message"),
    (
        ("policy", "Hardware policy must not be writable by the web service"),
        ("policy_parent", "Hardware policy directory must not be writable by the web service"),
        ("approval_dir", "Approval directory must not be writable by the web service"),
        ("approval_file", "Approval files must not be writable by the web service"),
        ("consumed_dir", "Consumed directory must be writable by the web service"),
    ),
)
def test_enforced_auth_requires_trusted_non_web_writable_inputs(
    monkeypatch, tmp_path, untrusted_path, message
):
    config = write_contract(tmp_path, approval=None)
    approval_file = config.approval_dir / f"{NONCE}.json"
    approval_file.write_text(json.dumps(approval()), encoding="utf-8")
    environ = {
        "PYCONLYSE_HARDWARE_POLICY_PATH": str(config.policy_path),
        "PYCONLYSE_HARDWARE_APPROVAL_DIR": str(config.approval_dir),
        "PYCONLYSE_HARDWARE_CONSUMED_DIR": str(config.consumed_dir),
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "true",
        "PYCONLYSE_PRODUCTION": "false",
    }
    target = {
        "policy": config.policy_path,
        "policy_parent": config.policy_path.parent,
        "approval_dir": config.approval_dir,
        "approval_file": approval_file,
        "consumed_dir": config.consumed_dir,
    }[untrusted_path].resolve()
    actual_access = os.access

    def web_service_access(path, mode):
        if mode == os.W_OK:
            if untrusted_path == "consumed_dir":
                return False
            return Path(path).resolve() in {target, config.consumed_dir.resolve()}
        return actual_access(path, mode)

    monkeypatch.setattr(hardware_authorization.os, "access", web_service_access)
    with pytest.raises(AuthorizationError, match=f"^{message}$") as exc:
        hardware_authorization.authorization_config_from_environment(environ)
    assert exc.value.status_code == 403


def test_local_opt_out_does_not_require_readonly_authorization_inputs(
    monkeypatch, tmp_path
):
    config = write_contract(tmp_path, approval=None)
    environ = {
        "PYCONLYSE_HARDWARE_POLICY_PATH": str(config.policy_path),
        "PYCONLYSE_HARDWARE_APPROVAL_DIR": str(config.approval_dir),
        "PYCONLYSE_HARDWARE_CONSUMED_DIR": str(config.consumed_dir),
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "false",
        "PYCONLYSE_PRODUCTION": "false",
    }
    monkeypatch.setattr(hardware_authorization.os, "access", lambda *_args: True)

    config = hardware_authorization.authorization_config_from_environment(environ)
    assert config.require_readonly_approvals is False


def test_approval_ttl_must_not_exceed_300_seconds(tmp_path):
    issued = datetime.now(timezone.utc)
    data = approval(expires_at=(issued + timedelta(seconds=301)).isoformat())
    data["issued_at"] = issued.isoformat()
    config = write_contract(tmp_path, approval=data)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=operation(), nonce=NONCE)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("subject,role", [("mallory", "operator"), (123, "operator"), ("alice", "reviewer")])
def test_subject_and_server_derived_role_are_not_caller_selectable(tmp_path, subject, role):
    config = write_contract(tmp_path, approval=approval(subject="alice", role="operator"))
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject=subject, role=role, operation=operation(), nonce=NONCE)
    assert exc.value.status_code in {403, 409}


def test_parallel_authorization_has_one_side_effect(tmp_path):
    config = write_contract(tmp_path, approval=approval())
    outcomes = []
    effects = []

    def run():
        try:
            authorize_operation(
                config,
                subject="alice",
                role="operator",
                operation=operation(),
                nonce=NONCE,
                before_side_effect=lambda: effects.append(True),
            )
            outcomes.append(True)
        except AuthorizationError:
            outcomes.append(False)

    threads = [threading.Thread(target=run) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count(True) == 1
    assert len(effects) == 1


@pytest.mark.parametrize("schema", [
    {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 4}, "min_items": 1, "max_items": 4},
    {"type": "string", "enum": ["start", "stop"]},
    {"type": "boolean"},
])
def test_bounded_optional_and_pattern_schemas_are_strict(tmp_path, schema):
    policy = {
        "version": 1,
        "subjects": {"alice": {"roles": ["operator"]}},
        "roles": {"operator": {}},
        "operations": [{
            "method": "POST", "route_id": "test.schema", "action": "execute",
            "targets": [{"device": "test", "command": "check"}], "roles": ["operator"],
            "args": schema,
        }],
    }
    config = write_contract(tmp_path, policy=policy)
    assert config.strict is True


def test_malformed_oversized_and_symlink_policy_are_rejected(tmp_path):
    malformed = tmp_path / "bad.json"
    malformed.write_text("not-json", encoding="utf-8")
    with pytest.raises(AuthorizationError) as exc:
        load_policy(malformed, strict=True)
    assert exc.value.status_code == 403

    oversized = tmp_path / "large.json"
    oversized.write_text("{" + "x" * (1024 * 1024 + 1) + "}", encoding="utf-8")
    with pytest.raises(AuthorizationError):
        load_policy(oversized, strict=True)

    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "policy-link.json"
    link.symlink_to(target)
    with pytest.raises(AuthorizationError):
        load_policy(link, strict=True)


def test_symlink_approval_is_rejected(tmp_path):
    op = operation()
    config = write_contract(tmp_path, approval=None)
    target = tmp_path / "approval-target.json"
    target.write_text(json.dumps(approval(op)), encoding="utf-8")
    (config.approval_dir / f"{NONCE}.json").symlink_to(target)
    with pytest.raises(AuthorizationError) as exc:
        authorize_operation(config, subject="alice", role="operator", operation=op, nonce=NONCE)
    assert exc.value.status_code == 428
