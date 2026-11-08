"""Unwired command-envelope foundation; disabled by default, Python 3.4.

No HTTP handler, NI imports, automatic retry, or production callback registry.
Only trusted local code may supply zero-argument callbacks. This is admission
and deduplication, not transport authentication or hardware qualification.
"""
import copy
import threading

from .runtime_identity import valid_hex


COMMAND_SCHEMA_VERSION = 1
NAMED_OPERATIONS = (
    "acquisition.initialize", "acquisition.deinitialize", "server.stop",
    "modulator.general.start", "modulator.general.stop",
)
ENVELOPE_FIELDS = frozenset((
    "schema_version", "command_id", "session_id", "expected_revision",
    "operation", "operator_confirmed",
))


class CommandRejected(ValueError):
    pass


def validate_envelope(envelope):
    """Reject arbitrary outputs, arguments, coercions, and missing confirmation."""
    if type(envelope) is not dict or set(envelope) != ENVELOPE_FIELDS:
        raise CommandRejected("EXACT_NAMED_COMMAND_ENVELOPE_REQUIRED")
    if (type(envelope["schema_version"]) is not int
            or envelope["schema_version"] != COMMAND_SCHEMA_VERSION):
        raise CommandRejected("INCOMPATIBLE_COMMAND_SCHEMA")
    if not valid_hex(envelope["command_id"], 32) or not valid_hex(envelope["session_id"], 32):
        raise CommandRejected("EXACT_SESSION_AND_COMMAND_ID_REQUIRED")
    revision = envelope["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise CommandRejected("EXACT_NONNEGATIVE_REVISION_REQUIRED")
    if envelope["operation"] not in NAMED_OPERATIONS:
        raise CommandRejected("UNKNOWN_NAMED_OPERATION")
    if envelope["operator_confirmed"] is not True:
        raise CommandRejected("EXPLICIT_OPERATOR_CONFIRMATION_REQUIRED")
    return dict(envelope)


class CommandAdmission(object):
    """At-most-once local dispatch attempt within one boot session.

    Indeterminate attempts are consumed before callback invocation and never
    replayed. A full bounded ledger rejects new IDs rather than evicting old IDs
    and inadvertently executing them again. Recovery remains a local operation,
    not an envelope option. The GUI and HTTP server do not instantiate this.
    """
    def __init__(self, runtime, callbacks=None, enabled=False, capacity=128):
        if type(enabled) is not bool or type(capacity) is not int or not 1 <= capacity <= 256:
            raise ValueError("Exact enabled flag and bounded command capacity required")
        callbacks = {} if callbacks is None else dict(callbacks)
        if any(name not in NAMED_OPERATIONS or not callable(callback)
               for name, callback in callbacks.items()):
            raise ValueError("Only reviewed names and trusted local callbacks are accepted")
        identity = runtime.snapshot()
        if not valid_hex(identity.get("session_id"), 32):
            raise ValueError("Runtime boot identity required")
        self._runtime = runtime
        self._session_id = identity["session_id"]
        self._callbacks = callbacks
        self._enabled = enabled
        self._capacity = capacity
        self._ledger = {}
        self._lock = threading.RLock()

    def submit(self, envelope):
        request = validate_envelope(envelope)
        with self._lock:
            if not self._enabled:
                raise CommandRejected("COMMAND_DISPATCH_DISABLED")
            # Do not present a cached acknowledgement from a previous boot as
            # current, even when the old command ID is known to this instance.
            session = self._runtime.snapshot().get("session_id")
            if request["session_id"] != self._session_id or session != self._session_id:
                raise CommandRejected("RUNTIME_SESSION_CHANGED")
            key = request["command_id"]
            previous = self._ledger.get(key)
            if previous is not None:
                if previous["request"] != request:
                    raise CommandRejected("COMMAND_ID_REUSED_WITH_DIFFERENT_REQUEST")
                result = copy.deepcopy(previous["response"])
                result["duplicate"] = True
                return result
            if request["operation"] not in self._callbacks:
                raise CommandRejected("OPERATION_NOT_INSTALLED")
            if len(self._ledger) >= self._capacity:
                raise CommandRejected("COMMAND_LEDGER_FULL_LOCAL_CONTROL_REQUIRED")
            response = dict(command_id=key, session_id=self._session_id,
                            operation=request["operation"], outcome="INDETERMINATE",
                            duplicate=False, hardware_acknowledged=False)
            self._ledger[key] = dict(request=request, response=response)
            try:
                self._runtime.fenced_local_request(
                    request["session_id"], request["expected_revision"],
                    self._callbacks[request["operation"]])
            except Exception as error:
                # Fence rejection and callback failure both consume this ID.
                # Never serialize exception text, callback results, or secrets.
                response["error_type"] = type(error).__name__
            else:
                # A queued runtime request is not an electrical acknowledgement.
                response["outcome"] = "DISPATCHED"
            return copy.deepcopy(response)
