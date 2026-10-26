"""Authenticated Everest telemetry sink with optional durable archive adapter.

Keep one latest value per publication and one receipt digest per relay. ACK means
accepted into this process's RAM, not durable storage. A receiver restart loses
live values and RAM deduplication state; the first signed message establishes a new FIFO
baseline, which may be greater than one when XP has already delivered messages.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import hmac
import math
import socketserver
import threading
import time
import uuid

from legacy.xp_acq_agent.elyse_agent.protocol import recv_message, send_message
from legacy.xp_acq_agent.elyse_agent.supervision_wire import validate_key
from legacy.xp_acq_agent.elyse_agent.telemetry_relay import DeadlineSocket, MAX_RELAY_FRAME, canonical, sign
from legacy.xp_acq_agent.elyse_agent.labview_telemetry import ALL_PUBLICATIONS, validate_packet
from legacy.xp_acq_agent.elyse_agent.shared_state import (
    BANKS, SNAPSHOT_PUBLICATION, expand_snapshot, validate_snapshot_packet,
)
from legacy.xp_acq_control.elyse_agent.cooling_safety import CoolingSafety, decode_publications
from legacy.xp_acq_control.elyse_agent.shared_state import (
    expand_snapshot as expand_python_snapshot,
)
from legacy.xp_acq_control.elyse_agent.native_telemetry import validate_standard_packet as validate_python_snapshot


class TelemetrySinkStore:
    def __init__(self, key, clock=time.monotonic, max_relays=64, permitted_producer_kind=None,
                 cooling=None, archive=None):
        if type(max_relays) is not int or not 1 <= max_relays <= 1024:
            raise ValueError("relay session limit must be an integer from 1 to 1024")
        self.key = validate_key(key)
        if permitted_producer_kind not in (None, 'fixture', 'copied_acquisition', 'python_acquisition', 'unified_acquisition'):
            raise ValueError('invalid producer-kind filter')
        self.permitted_producer_kind = permitted_producer_kind
        self.clock = clock
        self.lock = threading.RLock()
        self.ingress_lock = threading.Lock()
        self.archive = archive
        self.max_relays = max_relays
        self.receiver_session = uuid.uuid4().hex
        self.relays = {}
        self.latest = {}
        self.shared_snapshot_seen = False
        self.received = self.duplicates = 0
        self.closed = False
        self.python_session = None
        self.python_sequence = -1
        self.retired_python_sessions = set()
        self.unified_relay = None
        self.active_kind = None
        self.cooling = cooling if cooling is not None else CoolingSafety(clock=clock)
        bind = getattr(self.cooling, "bind_experiment_session", None)
        if bind is not None:
            bind(self.receiver_session)

    def accept(self, request):
        if type(request) is not dict or set(request) != {"body", "nonce", "signature"}:
            raise ValueError("invalid signed telemetry request")
        nonce = request["nonce"]
        if not isinstance(nonce, str) or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce):
            raise ValueError("invalid telemetry nonce")
        signed = dict(body=request["body"], nonce=nonce)
        signature = request["signature"]
        expected = sign(self.key, "ACQ-TELEMETRY-REQUEST-1", signed)
        if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
            raise ValueError("telemetry authentication failed")
        body = request["body"]
        if type(body) is not dict or set(body) != {
                "schema_version", "relay_id", "message_id", "received_utc_on_xp",
                "age_seconds_on_xp", "packet", "hardware_writes"}:
            raise ValueError("invalid telemetry body schema")
        relay_id, message_id = body["relay_id"], body["message_id"]
        if (type(body["schema_version"]) is not int or body["schema_version"] != 1
                or body["hardware_writes"] is not False
                or not isinstance(relay_id, str) or len(relay_id) != 32
                or any(c not in "0123456789abcdef" for c in relay_id)
                or type(message_id) is not int or not 1 <= message_id <= 9007199254740991
                or not isinstance(body["received_utc_on_xp"], str)
                or type(body["age_seconds_on_xp"]) not in (int, float)
                or not math.isfinite(body["age_seconds_on_xp"]) or body["age_seconds_on_xp"] < 0):
            raise ValueError("invalid telemetry body values")
        packet = body["packet"]
        is_snapshot = isinstance(packet, dict) and packet.get('publication') == SNAPSHOT_PUBLICATION
        is_python = isinstance(packet, dict) and packet.get('producer_kind') == 'python_acquisition'
        unified = self.permitted_producer_kind == 'unified_acquisition'
        if unified:
            expected_site = ('xp_unified_python_owner_27_banks' if is_python
                             else 'xp_unified_labview_bridge_27_banks')
            if (not is_snapshot or packet.get('producer_kind') not in ('python_acquisition', 'copied_acquisition')
                    or packet.get('source_site') != expected_site):
                raise ValueError('Unified receiver requires the single XP mode-arbitrated publisher')
        if is_python:
            if self.permitted_producer_kind not in ('python_acquisition', 'unified_acquisition') or not is_snapshot:
                raise ValueError('Python publisher requires explicit exclusive source selection')
            validate_python_snapshot(packet)
        elif is_snapshot:
            validate_snapshot_packet(packet)
        else:
            validate_packet(packet, ALL_PUBLICATIONS)
        if not unified and self.permitted_producer_kind is not None and packet['producer_kind'] != self.permitted_producer_kind:
            raise ValueError('producer kind is not permitted by this receiver')
        identity = dict(body)
        identity.pop("age_seconds_on_xp")  # Age increases on a legitimate retransmission.
        digest = hashlib.sha256(canonical(identity)).hexdigest()
        # Serialize ingress and close, but release the RAM/view lock during
        # durable spool I/O. A slow disk cannot hold snapshot/control readers.
        with self.ingress_lock:
            if self.closed:
                raise RuntimeError("telemetry store is closed")
            tracked = is_python or unified
            if tracked and packet["session_id"] in self.retired_python_sessions:
                raise ValueError("Retired Python producer session cannot overwrite current telemetry")
            if unified and packet['session_id'] == self.python_session and self.unified_relay != relay_id:
                raise ValueError('Unified boot cannot introduce a competing relay')
            previous = self.relays.get(relay_id)
            duplicate = previous is not None and message_id == previous["message_id"]
            if duplicate:
                if previous["digest"] != digest:
                    raise ValueError("telemetry ID reused with different content")
                self.duplicates += 1
            else:
                if previous is not None and message_id != previous["message_id"] + 1:
                    raise ValueError("telemetry FIFO message out of order")
                if previous is None and len(self.relays) >= self.max_relays:
                    # Do not evict an identity and silently accept its old replay.
                    raise ValueError("telemetry relay session capacity reached")
                if tracked and packet["session_id"] == self.python_session and packet["sequence"] <= self.python_sequence:
                    raise ValueError("Python snapshot sequence regressed across relay sessions")
                received_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                received_at = self.clock()
                if self.archive is not None:
                    self.archive.append_ingress(body, digest, self.receiver_session,
                                                self.received + 1, received_utc)
                self._commit_packet(body, packet, is_snapshot, is_python, tracked, unified,
                                    relay_id, message_id, digest, received_utc, received_at)
        ack_body = dict(accepted=True, duplicate=duplicate, relay_id=relay_id, message_id=message_id,
                        storage_mode="ram_latest", durable=False)
        signed_ack = dict(body=ack_body, nonce=nonce)
        return dict(signed_ack, signature=sign(self.key, "ACQ-TELEMETRY-ACK-1", signed_ack))

    def _commit_packet(self, body, packet, is_snapshot, is_python, tracked, unified,
                       relay_id, message_id, digest, received_utc, received_at):
        with self.lock:
            if tracked and packet["session_id"] != self.python_session:
                if self.python_session is not None:
                    self.retired_python_sessions.add(self.python_session)
                self.python_session = packet["session_id"]
            if tracked:
                self.python_sequence = packet["sequence"]
            if unified:
                self.unified_relay = relay_id
            self.active_kind = packet['producer_kind']
            entry = dict(body=copy.deepcopy(body), received_at=received_at, received_utc=received_utc)
            if is_snapshot:
                expanded = expand_python_snapshot(packet) if is_python else expand_snapshot(packet)
                for name, bank_packet in expanded.items():
                    bank_body = copy.deepcopy(body)
                    bank_body['packet'] = bank_packet
                    self.latest[name] = dict(body=bank_body, received_at=entry['received_at'],
                                             received_utc=received_utc)
                self.shared_snapshot_seen = True
            else:
                self.latest[packet["publication"]] = entry
            self.relays[relay_id] = dict(message_id=message_id, digest=digest)
            self.received += 1
            # Alarm transitions are evaluated on ingress, even with no
            # browser open. This receiver NEVER has shutdown authority.
            self.snapshot()

    def snapshot(self):
        with self.lock:
            now = self.clock()
            publications = {}
            for name, entry in self.latest.items():
                packet = copy.deepcopy(entry["body"]["packet"])
                age = entry["body"]["age_seconds_on_xp"] + max(0, now - entry["received_at"])
                packet.update(age_seconds=age, stale=age >= 2,
                              received_utc_on_everest=entry["received_utc"],
                              relay_id=entry["body"]["relay_id"], message_id=entry["body"]["message_id"])
                publications[name] = packet
            circuits, active = decode_publications(publications)
            identity = tuple((name, publications.get(name, {}).get("relay_id"),
                              publications.get(name, {}).get("message_id"))
                             for name in ("C3_IN_DIO96", "C4_IN_DIO96", "EPS"))
            # This receiver never owns NI or a VI stop route. General/EPS
            # alone cannot turn an old observer journal into a current HT
            # experiment. Python-owner alarms are projected from runtime_json
            # by the facade; VI retains its own original interlocks.
            self.cooling.observe(circuits, False, observation_id=identity)
            self.cooling.tick(automatic_stop_available=False)
            alarm = self.cooling.snapshot()
            alarm.update(receive_only=True, indications=circuits,
                interpretation="Receive-only VI indications; no local countdown or shutdown authority")
            source = "python_daqmx_acquisition" if (self.active_kind == 'python_acquisition'
                or self.permitted_producer_kind == 'python_acquisition') else "copied_labview_telemetry"
            return dict(source=source, hardware_writes=False,
                        hardware_writes_interpretation="Telemetry publication only, not authority of the XP card owner",
                        active_producer_kind=self.active_kind,
                        producer_session=self.python_session,
                        storage_mode="ram_latest", durable=False, history_available=self.archive is not None,
                        reset_on_restart=True, receiver_session=self.receiver_session,
                        archive=self.archive.status() if self.archive is not None else None,
                        relay_sessions=len(self.relays), max_relay_sessions=self.max_relays,
                        physical_measurements_verified=False, atomic_across_publications=False,
                        permitted_producer_kind=self.permitted_producer_kind,
                        received_this_process=self.received, duplicate_receipts=self.duplicates,
                        publications=publications,
                        cooling_safety=alarm,
                        shared_snapshot_seen=self.shared_snapshot_seen,
                        missing_publications=sorted(set(BANKS if self.shared_snapshot_seen else ALL_PUBLICATIONS) - set(publications)))

    def close(self):
        with self.ingress_lock, self.lock:
            if not self.closed:
                self.latest.clear()
                self.relays.clear()
                self.closed = True
        # Journal I/O/join must not hold ingress/RAM locks. An unfinished
        # journal remains owned and a later close retries that same owner.
        close = getattr(self.cooling, "close", None)
        if close is not None:
            if close(timeout=3) is False:
                raise RuntimeError("Cooling journal worker still owned; replacement refused")
        elif self.cooling.journal is not None:
            self.cooling.journal.close()


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.client_address[0] not in self.server.permitted_peers:
            return
        try:
            bounded = DeadlineSocket(self.request, time.monotonic() + 2)
            request = recv_message(bounded, MAX_RELAY_FRAME)
            reply = self.server.store.accept(request)
            send_message(bounded, reply, MAX_RELAY_FRAME)
        except Exception:
            # No trusted positive ACK: XP keeps the head for a later retry.
            return


class TelemetrySinkServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # server_close joins bounded in-flight handlers before the store is closed.
    daemon_threads = False
    allow_reuse_address = True

    def __init__(self, address, store, permitted_peers=("10.20.30.10",)):
        self.store, self.permitted_peers = store, tuple(permitted_peers)
        super().__init__(address, _Handler)
