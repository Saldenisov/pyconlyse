"""Authenticated, RAM-only Everest telemetry sink; no control or archive adapter.

Keep one latest value per publication and one receipt digest per relay. ACK means
accepted into this process's RAM, not durable storage. A receiver restart loses
values and deduplication state; the first signed message establishes a new FIFO
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


class TelemetrySinkStore:
    def __init__(self, key, clock=time.monotonic, max_relays=64, permitted_producer_kind=None):
        if type(max_relays) is not int or not 1 <= max_relays <= 1024:
            raise ValueError("relay session limit must be an integer from 1 to 1024")
        self.key = validate_key(key)
        if permitted_producer_kind not in (None, 'fixture', 'copied_acquisition'):
            raise ValueError('invalid producer-kind filter')
        self.permitted_producer_kind = permitted_producer_kind
        self.clock = clock
        self.lock = threading.RLock()
        self.max_relays = max_relays
        self.receiver_session = uuid.uuid4().hex
        self.relays = {}
        self.latest = {}
        self.shared_snapshot_seen = False
        self.received = self.duplicates = 0
        self.closed = False

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
        if is_snapshot:
            validate_snapshot_packet(packet)
        else:
            validate_packet(packet, ALL_PUBLICATIONS)
        if self.permitted_producer_kind is not None and packet['producer_kind'] != self.permitted_producer_kind:
            raise ValueError('producer kind is not permitted by this receiver')
        identity = dict(body)
        identity.pop("age_seconds_on_xp")  # Age increases on a legitimate retransmission.
        digest = hashlib.sha256(canonical(identity)).hexdigest()
        with self.lock:
            if self.closed:
                raise RuntimeError("telemetry store is closed")
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
                received_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                entry = dict(body=copy.deepcopy(body), received_at=self.clock(), received_utc=received_utc)
                if is_snapshot:
                    for name, bank_packet in expand_snapshot(packet).items():
                        bank_body = copy.deepcopy(body)
                        bank_body['packet'] = bank_packet
                        self.latest[name] = dict(body=bank_body, received_at=entry['received_at'],
                                                 received_utc=received_utc)
                    self.shared_snapshot_seen = True
                else:
                    self.latest[packet["publication"]] = entry
                self.relays[relay_id] = dict(message_id=message_id, digest=digest)
                self.received += 1
        ack_body = dict(accepted=True, duplicate=duplicate, relay_id=relay_id, message_id=message_id,
                        storage_mode="ram_latest", durable=False)
        signed_ack = dict(body=ack_body, nonce=nonce)
        return dict(signed_ack, signature=sign(self.key, "ACQ-TELEMETRY-ACK-1", signed_ack))

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
            return dict(source="copied_labview_telemetry", hardware_writes=False,
                        storage_mode="ram_latest", durable=False, history_available=False,
                        reset_on_restart=True, receiver_session=self.receiver_session,
                        relay_sessions=len(self.relays), max_relay_sessions=self.max_relays,
                        physical_measurements_verified=False, atomic_across_publications=False,
                        permitted_producer_kind=self.permitted_producer_kind,
                        received_this_process=self.received, duplicate_receipts=self.duplicates,
                        publications=publications,
                        shared_snapshot_seen=self.shared_snapshot_seen,
                        missing_publications=sorted(set(BANKS if self.shared_snapshot_seen else ALL_PUBLICATIONS) - set(publications)))

    def close(self):
        with self.lock:
            if not self.closed:
                self.latest.clear()
                self.relays.clear()
                self.closed = True


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
