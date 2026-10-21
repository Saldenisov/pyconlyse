"""Bounded installation-local NI ownership marker; Python 3.4.

No PID polling, device discovery, driver import, telemetry, or automatic stale
owner cleanup. A dead parent does NOT prove absent native workers or hardware
owners. Recovery requires a separately qualified, explicitly injected checker;
the production default has none and fails closed. Different configurations or
LabVIEW copies are outside this marker's cooperative ownership scope.
"""
import json
import os
import threading
import uuid

from .runtime_identity import valid_hex


MARKER_KIND = "ELYSE_ACQUISITION_OWNERSHIP_V1"
MAX_MARKER_BYTES = 4096


class RecoveryRequired(RuntimeError):
    pass


class OwnershipMarker(object):
    def __init__(self, path, session_id, build_id, process_id=None, quiescence_checker=None):
        if not isinstance(path, str) or not os.path.isabs(path):
            raise ValueError("Absolute installation-local ownership marker path required")
        if not valid_hex(session_id, 32) or not valid_hex(build_id, 64):
            raise ValueError("Qualified runtime identity required")
        if quiescence_checker is not None and not callable(quiescence_checker):
            raise ValueError("Recovery checker must be callable or unavailable")
        process_id = os.getpid() if process_id is None else process_id
        if type(process_id) is not int or process_id <= 0:
            raise ValueError("Positive current process identifier required")
        self.path, self.session_id, self.build_id = path, session_id, build_id
        self.process_id = process_id
        self.quiescence_checker = quiescence_checker
        self._owned_bytes = None
        self._lock = threading.RLock()
        self._recovered = False

    def _read(self):
        try:
            with open(self.path, "rb") as source:
                raw = source.read(MAX_MARKER_BYTES + 1)
        except OSError as error:
            if getattr(error, "errno", None) == 2:
                return None
            raise RecoveryRequired("Ownership marker cannot be read: " + str(error))
        if len(raw) > MAX_MARKER_BYTES:
            raise RecoveryRequired("Oversized or unrelated ownership marker; preserved")
        return raw

    @staticmethod
    def _decode(raw):
        try:
            record = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise RecoveryRequired("Malformed or unrelated ownership marker; preserved")
        if (not isinstance(record, dict)
                or set(record) != {"kind", "session_id", "build_id", "owner_pid", "nonce"}
                or record["kind"] != MARKER_KIND
                or not valid_hex(record["session_id"], 32)
                or not valid_hex(record["build_id"], 64)
                or not valid_hex(record["nonce"], 32)
                or type(record["owner_pid"]) is not int or record["owner_pid"] <= 0):
            raise RecoveryRequired("Unqualified or unrelated ownership marker; preserved")
        return record

    def snapshot(self):
        with self._lock:
            try:
                raw = self._read()
                if raw is None:
                    required = self._owned_bytes is not None
                    reason = ("CURRENT_OWNERSHIP_MARKER_MISSING" if required else
                              "EXPLICIT_RECOVERY_VERIFIED_CARDS_STILL_UNINITIALIZED" if self._recovered else
                              "NO_UNRELEASED_OWNERSHIP_MARKER")
                elif self._owned_bytes is not None and raw == self._owned_bytes:
                    required, reason = False, "CURRENT_SESSION_OWNS_DIRTY_MARKER"
                else:
                    self._decode(raw)
                    required, reason = True, "UNRELEASED_PRIOR_OR_OTHER_OWNER_MARKER"
            except RecoveryRequired as error:
                required, reason = True, str(error)
            return dict(required=required, reason=reason, protection_active=True,
                        scope="installation_config_path_only_not_machine_wide_NI_exclusion",
                        owns_current_marker=self._owned_bytes is not None,
                        recovery_checker_available=self.quiescence_checker is not None,
                        orphan_absence_verified=False)

    def acquire(self):
        """Exclusive create BEFORE NI factory; an existing marker is never replaced."""
        with self._lock:
            if self._owned_bytes is not None:
                raise RecoveryRequired("Current session already holds an ownership marker")
            payload = dict(kind=MARKER_KIND, session_id=self.session_id, build_id=self.build_id,
                           owner_pid=self.process_id, nonce=uuid.uuid4().hex)
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if len(raw) > MAX_MARKER_BYTES:
                raise RecoveryRequired("Ownership marker exceeds bounded format")
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except OSError as error:
                raise RecoveryRequired("Ownership marker exclusive create refused; existing state preserved: " + str(error))
            try:
                with os.fdopen(descriptor, "wb") as target:
                    target.write(raw)
                    target.flush()
                    os.fsync(target.fileno())
            except Exception as error:
                # Even a partial marker remains dirty. No guessed cleanup.
                raise RecoveryRequired("Ownership marker persistence failed; marker retained: " + str(error))
            self._owned_bytes = raw
            self._recovered = False

    def release_after_cleanup(self, resources_quiescent=False):
        """Caller has closed all NI tasks/native children successfully.

        Only this exact session's bytes may be unlinked. The cooperative
        exclusive-create protocol assumes no external editor replaces a live
        marker; a changed/unrelated marker is never overwritten or removed.
        """
        with self._lock:
            if self._owned_bytes is None:
                return False  # Stopping a cold blocked server preserves prior state.
            if resources_quiescent is not True:
                raise ValueError("Explicit successful NI/native-resource cleanup confirmation required")
            if self._read() != self._owned_bytes:
                raise RecoveryRequired("Current marker changed/missing; cleanup cannot certify clean ownership")
            os.unlink(self.path)
            self._owned_bytes = None
            return True

    def recover(self, electrical_off_confirmed=False):
        """Explicit local acknowledgement, never initialization or command replay."""
        with self._lock:
            if electrical_off_confirmed is not True:
                raise ValueError("Explicit verified local electrical OFF confirmation required")
            if self._owned_bytes is not None:
                raise RecoveryRequired("Current session owns resources; use normal cleanup")
            raw = self._read()
            if raw is None:
                raise RecoveryRequired("No prior marker to recover")
            record = self._decode(raw)
            if record["session_id"] == self.session_id:
                raise RecoveryRequired("Current-session marker cannot be recovered as a prior owner")
            if record["owner_pid"] == self.process_id:
                raise RecoveryRequired("Current-process marker cannot be recovered as an absent prior owner")
            if self.quiescence_checker is None:
                raise RecoveryRequired("Qualified process/native-child/NI-owner quiescence checker unavailable; marker preserved")
            result = self.quiescence_checker(dict(record))
            facts = ("verified", "owner_process_absent", "native_children_absent", "ni_competitors_absent")
            if (not isinstance(result, dict) or any(result.get(name) is not True for name in facts)
                    or not isinstance(result.get("method"), str) or not result["method"].strip()):
                raise RecoveryRequired("Quiescence proof incomplete; parent PID absence alone is insufficient")
            if self._read() != raw:
                raise RecoveryRequired("Marker changed during recovery verification; preserved")
            os.unlink(self.path)
            self._recovered = True
            return dict(required=False, reason="EXPLICIT_RECOVERY_VERIFIED_CARDS_STILL_UNINITIALIZED",
                        protection_active=True)
