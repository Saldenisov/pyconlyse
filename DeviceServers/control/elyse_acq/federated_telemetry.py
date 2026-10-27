"""Two authenticated local owners -> one non-atomic 27-bank Everest view.

Optional receiver mode. Each owner has independent keys, relay/session FIFO,
retired boots and source ages. A healthy peer never freshens or replaces a
missing/stale peer. No NI, PSP, Tango or network operation occurs in this store.
"""
import copy
import datetime
import hashlib
import hmac
import threading
import time
import uuid
import json
from pathlib import Path

from legacy.xp_acq_control.elyse_agent.federation_wire import (
    ROLES, OWNED_BANKS, PUBLICATION, validate_owner_frame, expand_owner_frame, finite, hex_id,
)
from legacy.xp_acq_control.elyse_agent.shared_state import BANKS
from legacy.xp_acq_control.elyse_agent.standard_banks import schemas, UNAVAILABLE
from legacy.xp_acq_control.elyse_agent.cooling_safety import CoolingSafety, decode_publications
from legacy.xp_acq_agent.elyse_agent.supervision_wire import validate_key
from legacy.xp_acq_agent.elyse_agent.telemetry_relay import canonical, sign


def load_federation_configuration(path, commands_enabled=False):
    """Local explicit configuration; never discover an endpoint or share a key."""
    path = Path(path).resolve()
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate federation configuration field")
            result[key] = value
        return result
    raw = path.read_bytes()
    if len(raw) > 16384:
        raise ValueError("Federation configuration too large")
    config = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    if (type(config) is not dict or set(config) != {"schema_version", "owners"}
            or type(config["schema_version"]) is not int or config["schema_version"] != 1
            or type(config["owners"]) is not dict or set(config["owners"]) != set(ROLES)
            or type(commands_enabled) is not bool):
        raise ValueError("Exact two-owner federation configuration required")
    result, keys = {}, []
    for role in ROLES:
        item = config["owners"][role]
        expected_host = "10.20.30.10" if role == "acquisition" else "10.20.30.2"
        if (type(item) is not dict or set(item) != {
                "host", "port", "read_key_file", "command_key_file", "commands_enabled"}
                or item["host"] != expected_host or type(item["port"]) is not int
                or not 1024 <= item["port"] <= 65535 or type(item["commands_enabled"]) is not bool
                or not isinstance(item["read_key_file"], str) or not item["read_key_file"]
                or not isinstance(item["command_key_file"], str)):
            raise ValueError("Fixed owner endpoint and explicit key paths required")
        read_key = validate_key((path.parent / item["read_key_file"]).read_bytes().strip())
        keys.append(read_key)
        enabled = commands_enabled and item["commands_enabled"]
        command_key = None
        if enabled:
            if not item["command_key_file"]:
                raise ValueError("Enabled owner commands require a separate key file")
            command_key = validate_key((path.parent / item["command_key_file"]).read_bytes().strip())
            keys.append(command_key)
        result[role] = dict(host=item["host"], port=item["port"], read_key=read_key,
                            command_key=command_key, enabled=enabled)
    if len(keys) != len(set(keys)):
        raise ValueError("Every active owner telemetry/command key must differ")
    return result


def missing_bank(name, reason):
    owner = next((role for role in ROLES if name in OWNED_BANKS[role]), None)
    return dict(publication=name, owner=owner, data=None, lv_type=copy.deepcopy(schemas()[name]),
        error=dict(status=True, code=UNAVAILABLE, source=reason), stale=True,
        age_seconds=None, session_id=None, sequence=None, source_seconds_1904=None,
        producer_kind="unavailable", hardware_acknowledged=False)


def _video_capture_key(video):
    return (video.get("source_session_id") if video["source"] == "labview_supervision_ni1409" else "native",
            video["capture_session_id"])


class FederatedTelemetryStore(object):
    def __init__(self, owner_keys, clock=time.monotonic, max_relays=64, cooling=None, archive=None):
        if type(owner_keys) is not dict or set(owner_keys) != set(ROLES):
            raise ValueError("Distinct configured keys for both orchestrator owners required")
        self.keys = dict((role, validate_key(key)) for role, key in owner_keys.items())
        if self.keys["acquisition"] == self.keys["supervision"]:
            raise ValueError("Owner telemetry keys must differ")
        if type(max_relays) is not int or not 1 <= max_relays <= 1024:
            raise ValueError("Bounded per-owner relay capacity required")
        self.clock, self.max_relays, self.archive = clock, max_relays, archive
        self.receiver_session = uuid.uuid4().hex
        self.lock, self.ingress_lock = threading.RLock(), threading.Lock()
        self.closed, self.received, self.duplicates = False, 0, 0
        self.owners = dict((role, dict(session=None, sequence=-1, relay=None,
            retired=set(), relays={}, session_relays={}, seen_sequences={},
            latest=None, last_observation=None, video=None, retired_video_sessions=set(),
            received=0, duplicates=0)) for role in ROLES)
        self.cooling = cooling if cooling is not None else CoolingSafety(clock=clock)
        self.cooling.bind_experiment_session(self.receiver_session)

    def accept(self, request):
        if type(request) is not dict or set(request) != {"body", "nonce", "signature"}:
            raise ValueError("Exact signed owner request required")
        body, nonce = request["body"], request["nonce"]
        if (not hex_id(nonce) or type(body) is not dict or set(body) != {
                "schema_version", "relay_id", "message_id", "received_utc_on_xp",
                "age_seconds_on_xp", "packet", "hardware_writes"}):
            raise ValueError("Exact owner relay envelope required")
        frame = body["packet"]
        role = frame.get("owner") if type(frame) is dict else None
        if not isinstance(role, str) or role not in self.keys:
            raise ValueError("Unknown authenticated telemetry owner")
        signed = dict(body=body, nonce=nonce)
        expected = sign(self.keys[role], "ACQ-TELEMETRY-REQUEST-1", signed)
        if not isinstance(request["signature"], str) or not hmac.compare_digest(request["signature"], expected):
            raise ValueError("Owner telemetry authentication failed")
        validate_owner_frame(frame)
        relay_id, message_id = body["relay_id"], body["message_id"]
        if (type(body["schema_version"]) is not int or body["schema_version"] != 1
                or body["hardware_writes"] is not False or not hex_id(relay_id)
                or type(message_id) is not int or not 1 <= message_id <= 9007199254740991
                or not isinstance(body["received_utc_on_xp"], str)
                or not finite(body["age_seconds_on_xp"]) or body["age_seconds_on_xp"] < 0):
            raise ValueError("Invalid owner relay identity or delivery age")
        identity = dict(body)
        identity.pop("age_seconds_on_xp")  # A legitimate immutable-head retry ages.
        digest = hashlib.sha256(canonical(identity)).hexdigest()
        with self.ingress_lock:
            if self.closed:
                raise RuntimeError("Federated telemetry store is closed")
            owner = self.owners[role]
            if frame["session_id"] in owner["retired"]:
                raise ValueError("Retired owner boot cannot overwrite its successor")
            if frame["session_id"] in owner["session_relays"] and owner["session_relays"][frame["session_id"]] != relay_id:
                raise ValueError("One owner boot cannot introduce a competing relay")
            previous = owner["relays"].get(relay_id)
            duplicate = previous is not None and previous["message_id"] == message_id
            if duplicate:
                if previous["digest"] != digest:
                    raise ValueError("Owner relay ID reused with different content")
                with self.lock:
                    self.duplicates += 1
                    owner["duplicates"] += 1
            else:
                if previous is not None and message_id != previous["message_id"] + 1:
                    raise ValueError("Owner relay FIFO regressed or skipped")
                if previous is not None and previous["session_id"] != frame["session_id"]:
                    raise ValueError("A relay identity cannot be reused by another owner boot")
                if previous is None and len(owner["relays"]) >= self.max_relays:
                    raise ValueError("Per-owner relay capacity reached; no replay-state eviction")
                if frame["sequence"] <= owner["seen_sequences"].get(frame["session_id"], -1):
                    raise ValueError("Owner source sequence regressed")
                observed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                observed_at = self.clock()
                mode_changed = bool(frame["session_id"] == owner["session"] and owner["latest"] is not None
                    and owner["latest"]["body"]["packet"]["source_mode"] != frame["source_mode"])
                if mode_changed and owner["video"] is not None and len(owner["retired_video_sessions"]) >= self.max_relays:
                    raise ValueError("Camera replay-state capacity reached; source mode change refused")
                video_update = self._plan_video(owner, frame, body["age_seconds_on_xp"], observed_at)
                if self.archive is not None:
                    self.archive.append_ingress(body, digest, self.receiver_session,
                                                self.received + 1, observed_utc)
                with self.lock:
                    entry = dict(body=copy.deepcopy(body), received_at=observed_at, received_utc=observed_utc)
                    owner["last_observation"] = entry
                    # An uninitialized, empty or already-stale new boot is a
                    # diagnostic observation, not authority to retire a peer's
                    # healthy current generation. First current data promotes it.
                    current_data = frame["source_mode"] != "UNAVAILABLE" and (
                        any(record["data"] is not None and record["source_age_seconds"]
                            + body["age_seconds_on_xp"] < 2 for record in frame["banks"])
                        or frame["counter_part"] is not None and frame["counter_part"]["source_age_seconds"]
                            + body["age_seconds_on_xp"] < 2
                        or frame["video_frame"] is not None and frame["video_frame"]["source_age_seconds"]
                            + body["age_seconds_on_xp"] < 2)
                    if frame["session_id"] == owner["session"] or current_data:
                        if frame["session_id"] != owner["session"]:
                            if owner["session"] is not None:
                                owner["retired"].add(owner["session"])
                            owner["session"] = frame["session_id"]
                            owner["video"], owner["retired_video_sessions"] = None, set()
                        elif mode_changed and owner["video"] is not None:
                            owner["retired_video_sessions"].add(owner["video"]["capture_key"])
                            owner["video"] = None
                        owner.update(sequence=frame["sequence"], relay=relay_id, latest=entry)
                        if video_update is not None:
                            prior_video = owner["video"]
                            if prior_video is not None and prior_video["capture_key"] != video_update["capture_key"]:
                                owner["retired_video_sessions"].add(prior_video["capture_key"])
                            owner["video"] = video_update
                    owner["relays"][relay_id] = dict(message_id=message_id, digest=digest,
                                                    session_id=frame["session_id"])
                    owner["session_relays"][frame["session_id"]] = relay_id
                    owner["seen_sequences"][frame["session_id"]] = frame["sequence"]
                    owner["received"] += 1
                    self.received += 1
        ack_body = dict(accepted=True, duplicate=duplicate, relay_id=relay_id,
                        message_id=message_id, storage_mode="ram_latest", durable=False)
        ack = dict(body=ack_body, nonce=nonce)
        return dict(ack, signature=sign(self.keys[role], "ACQ-TELEMETRY-ACK-1", ack))

    def _plan_video(self, owner, frame, queue_age, observed_at):
        video = frame["video_frame"]
        if video is None:
            return None
        same_boot = frame["session_id"] == owner["session"]
        prior = owner["video"] if same_boot and owner["video"] is not None and owner["video"]["source_mode"] == frame["source_mode"] else None
        capture = _video_capture_key(video)
        if same_boot and capture in owner["retired_video_sessions"]:
            raise ValueError("Retired camera capture session cannot overwrite its successor")
        identity = copy.deepcopy(video)
        identity.pop("source_age_seconds")
        digest = hashlib.sha256(canonical(identity)).hexdigest()
        age = video["source_age_seconds"] + queue_age
        if prior is not None and prior["capture_key"] == capture:
            if video["sequence"] < prior["sequence"]:
                raise ValueError("Camera frame sequence regressed within its capture session")
            if video["sequence"] == prior["sequence"]:
                if digest != prior["digest"]:
                    raise ValueError("Camera frame identity reused with different bytes or metadata")
                # A status heartbeat carrying the same capture cannot freshen
                # it, even if its caller incorrectly repeats source_age=0.
                age = max(age, prior["base_age"] + max(0., observed_at - prior["received_at"]))
        elif prior is not None:
            if len(owner["retired_video_sessions"]) >= self.max_relays:
                raise ValueError("Camera capture replay-state capacity reached")
            if age >= 2:
                return None  # Stale new worker cannot replace a healthy capture.
        return dict(frame=copy.deepcopy(video), capture_session_id=video["capture_session_id"], capture_key=capture,
                    sequence=video["sequence"], digest=digest, base_age=age,
                    received_at=observed_at, owner_session_id=frame["session_id"],
                    source_mode=frame["source_mode"])

    def _owner_view(self, role, now):
        owner = self.owners[role]
        entry = owner["latest"]
        candidate = owner["last_observation"]
        candidate_frame = candidate["body"]["packet"] if candidate is not None else {}
        if entry is None:
            return dict(owner=role, quality="WAITING", session_id=None, sequence=None,
                source_mode="UNAVAILABLE", age_seconds=None, source_current=False,
                observed_candidate_session=candidate_frame.get("session_id"),
                candidate_requires_current_data=bool(candidate),
                received_this_process=owner["received"], duplicate_receipts=owner["duplicates"])
        frame = entry["body"]["packet"]
        age = entry["body"]["age_seconds_on_xp"] + max(0., now - entry["received_at"])
        present = any(record["data"] is not None for record in frame["banks"]) or frame["counter_part"] is not None
        video = owner["video"]
        video_current = bool(video is not None and video["owner_session_id"] == frame["session_id"]
            and video["source_mode"] == frame["source_mode"]
            and video["base_age"] + max(0., now - video["received_at"]) < 2)
        available = (frame["source_mode"] != "UNAVAILABLE" and (
            any(record["data"] is not None and record["source_age_seconds"] + age < 2
                for record in frame["banks"])
            or frame["counter_part"] is not None and frame["counter_part"]["source_age_seconds"] + age < 2
            or video_current))
        return dict(owner=role, quality=("STALE" if age >= 2 or present and not available
                                        else "FRESH" if available else "UNAVAILABLE"),
            session_id=frame["session_id"], sequence=frame["sequence"], source_mode=frame["source_mode"],
            age_seconds=age, source_current=bool(age < 2 and available),
            observed_candidate_session=candidate_frame.get("session_id"),
            candidate_requires_current_data=candidate_frame.get("session_id") != frame["session_id"],
            received_utc_on_everest=entry["received_utc"], relay_id=entry["body"]["relay_id"],
            source_identity=copy.deepcopy(frame.get("source_identity")),
            received_this_process=owner["received"], duplicate_receipts=owner["duplicates"])

    def owner_current(self, role, session_id=None, native=False):
        if role not in ROLES:
            return False
        with self.lock:
            view = self._owner_view(role, self.clock())
            return (view["source_current"] and (session_id is None or view["session_id"] == session_id)
                    and (not native or view["source_mode"] == "PYTHON_NATIVE"))

    def _counter_bank(self, views, now):
        parts, ages, sessions, sequences = [], {}, {}, {}
        for role in ROLES:
            if not views[role]["source_current"]:
                return missing_bank("C1011NI6602", "BOTH_COUNTER_OWNERS_MUST_BE_CURRENT")
            frame = self.owners[role]["latest"]["body"]["packet"]
            part = frame["counter_part"]
            if part is None or part["pending_selector"] is not False or part["selector"] != -1:
                return missing_bank("C1011NI6602", "EXPLICIT_IDLE_COUNTER_MEMORIES_REQUIRED")
            age = part["source_age_seconds"] + views[role]["age_seconds"]
            if age >= 2:
                return missing_bank("C1011NI6602", "COUNTER_OWNER_MEMORY_STALE")
            parts.extend(part["values"])
            ages[role], sessions[role], sequences[role] = age, frame["session_id"], frame["sequence"]
        return dict(publication="C1011NI6602", owner="composite", data=copy.deepcopy(parts) + [-1.],
            lv_type=copy.deepcopy(schemas()["C1011NI6602"]),
            error=dict(status=False, code=0, source=""), stale=False, age_seconds=max(ages.values()),
            session_id=None, sequence=self.received, source_seconds_1904=None,
            producer_kind="federated_counter_command_memory", component_sessions=sessions,
            component_sequences=sequences, component_ages_seconds=ages,
            hardware_acknowledged=False, atomic_across_owners=False,
            interpretation="Two current command memories; selector -1 is explicit no-pending software state, not an ACK")

    def snapshot(self):
        with self.lock:
            now = self.clock()
            views = dict((role, self._owner_view(role, now)) for role in ROLES)
            publications = dict((bank, missing_bank(bank, "BANK_SOURCE_NOT_QUALIFIED")) for bank in BANKS)
            for role in ROLES:
                entry = self.owners[role]["latest"]
                if entry is None:
                    for bank in OWNED_BANKS[role]:
                        publications[bank] = missing_bank(bank, "OWNER_NOT_SEEN:" + role)
                    continue
                for bank, packet in expand_owner_frame(entry["body"]["packet"]).items():
                    age = packet["source_age_seconds"] + views[role]["age_seconds"]
                    packet.update(age_seconds=age, stale=age >= 2,
                        received_utc_on_everest=entry["received_utc"],
                        relay_id=entry["body"]["relay_id"], message_id=entry["body"]["message_id"],
                        hardware_acknowledged=False)
                    publications[bank] = packet
            publications["C1011NI6602"] = self._counter_bank(views, now)
            circuits, unused = decode_publications(publications)
            identity = tuple((role, view["session_id"], view["sequence"]) for role, view in sorted(views.items()))
            self.cooling.observe(circuits, False, observation_id=identity)
            self.cooling.tick(automatic_stop_available=False)
            alarm = self.cooling.snapshot()
            alarm.update(receive_only=True, indications=circuits,
                interpretation="Federated receiver indication projection; no local shutdown authority")
            return dict(source="federated_orchestrators", hardware_writes=False,
                hardware_writes_interpretation="Telemetry only; local owners retain command authority",
                active_producer_kind="federated_orchestrators", producer_session=None,
                storage_mode="ram_latest", durable=False, history_available=self.archive is not None,
                reset_on_restart=True, receiver_session=self.receiver_session,
                archive=self.archive.status() if self.archive is not None else None,
                relay_sessions=sum(len(o["relays"]) for o in self.owners.values()),
                max_relay_sessions=self.max_relays * len(ROLES),
                physical_measurements_verified=False, atomic_across_publications=False,
                permitted_producer_kind="federated_orchestrators", received_this_process=self.received,
                duplicate_receipts=self.duplicates, publications=publications,
                owners=views, video_metadata=self._video_view(now, include_data=False),
                supervision_counter=self._counter_view(now),
                cooling_safety=alarm, shared_snapshot_seen=True,
                missing_publications=[], unavailable_owners=[role for role in ROLES if not views[role]["source_current"]])

    def _counter_view(self, now):
        """Independent 16-value memory observation; never a legacy-bank fallback.

        Pending selectors remain visible as observed state. They do not become
        hardware acknowledgements or permission to combine the two owners.
        """
        owner = self.owners["supervision"]
        entry = owner["latest"]
        frame = entry["body"]["packet"] if entry is not None else {}
        part = frame.get("counter_part")
        age = None if part is None else (part["source_age_seconds"]
            + entry["body"]["age_seconds_on_xp"] + max(0., now - entry["received_at"]))
        available = bool(not self.closed and part is not None and age < 2
            and frame.get("source_mode") in ("PYTHON_NATIVE", "LABVIEW_BRIDGE"))
        return dict(owner="supervision", available=available, stale=not available,
            values=copy.deepcopy(part["values"]) if available else None,
            source=part["source"] if part is not None else None,
            selector=part["selector"] if part is not None else None,
            pending_selector=part["pending_selector"] if part is not None else None,
            age_seconds=age, session_id=frame.get("session_id"),
            sequence=frame.get("sequence"), source_mode=frame.get("source_mode", "UNAVAILABLE"),
            source_identity=copy.deepcopy(frame.get("source_identity")),
            read_only=True, hardware_acknowledged=False, physical_measurements_verified=False,
            interpretation="Observed counter control memory, not hardware timing readback")

    def counter_snapshot(self):
        with self.lock:
            return self._counter_view(self.clock())

    def _video_view(self, now, include_data):
        owner = self.owners["supervision"]
        video = owner["video"]
        if video is None:
            return dict(owner="supervision", available=False, stale=True,
                        session_id=owner["session"], age_seconds=None, frame=None) if include_data else dict(
                            owner="supervision", available=False, stale=True, session_id=owner["session"], age_seconds=None)
        age = video["base_age"] + max(0., now - video["received_at"])
        mode = owner["latest"]["body"]["packet"]["source_mode"] if owner["latest"] is not None else None
        available = bool(not self.closed and mode in ("PYTHON_NATIVE", "LABVIEW_BRIDGE")
            and video["source_mode"] == mode and video["owner_session_id"] == owner["session"] and age < 2)
        frame = video["frame"]
        value = dict(owner="supervision", available=available, stale=not available,
            session_id=owner["session"], capture_session_id=video["capture_session_id"],
            sequence=video["sequence"], age_seconds=age, width=frame["width"], height=frame["height"],
            pixel_type=frame["pixel_type"], encoding=frame["encoding"], channel=frame["channel"],
            processing=frame["processing"], observed_utc=frame["observed_utc"], hardware_acknowledged=False)
        value.update(source=frame["source"], source_mode=video["source_mode"],
                     source_session_id=frame.get("source_session_id"))
        if include_data:
            value["frame"] = copy.deepcopy(frame) if available else None
        return value

    def video_snapshot(self):
        with self.lock:
            return self._video_view(self.clock(), include_data=True)

    def close(self):
        with self.ingress_lock, self.lock:
            self.closed = True
            for owner in self.owners.values():
                owner["latest"], owner["video"] = None, None
        close = getattr(self.cooling, "close", None)
        if close is not None and close(timeout=3) is False:
            raise RuntimeError("Federated cooling journal remains owned")
