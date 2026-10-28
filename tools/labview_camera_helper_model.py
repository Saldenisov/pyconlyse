"""Offline camera lifecycle/work-budget proof. Stdlib CPython3.4; no NI API.

Snapshot evaluation is source-graph analysis, never LabVIEW execution.
"""

import argparse
import hashlib
import itertools
import json

MASK32 = (1 << 32) - 1
EMPTY_GATE = (0, 0, 0, 0, False, False)
EPOCH_NATIVE_SHA256 = "f6bb97d1eab2f87ca932391219fefb04e88e089db9057445f814b1d981ebcc01"
SNAPSHOT_SHA256 = "ae692fbaf4cd47e9f4264db37657405c19692caacfb6ad593320483976bb134d"
SETUP_NATIVE_SHA256 = "1de01a7e5d18fa231866dfe257dc268b067de58e4eefa54a9b10438682cf202c"
SETUP_SNAPSHOT_SHA256 = (
    "82b097c58e28cf990b10c6ba4fc53761ec9009b285f61f5f38d083082905b473"
)


def decode_scalar(raw, width):
    """Decode scalar at offset0; permit one trailing zero from native templates."""
    if width not in (1, 4, 16) or len(raw) not in (width, width + 1):
        raise ValueError("Unsupported native scalar width")
    if any(raw[width:]):
        raise ValueError("Nonzero byte outside native scalar width")
    return int.from_bytes(raw[:width], "big")


def epoch_transition(state, action, requested, channel=0, setup_ok=False, now=0):
    """Private state is (run,capture,actual_channel,valid); full U32 channel."""
    run, capture, old_channel, valid = state
    same = requested != 0 and requested == run
    if action == 0:
        result = (requested, 0, 0, False)
    elif action == 1 and same:
        if setup_ok and 0 <= channel <= MASK32:
            result = (run, now, channel, now >= run and now != 0)
        else:
            result = (run, capture, old_channel, False)
    elif action == 3 and same:
        result = (run, capture, old_channel, False)
    else:
        result = state
    reply_valid = (
        result[3]
        and requested != 0
        and requested == result[0]
        and action in (0, 1, 2, 3)
    )
    return result, (result[1], result[2], bool(reply_valid))


def frame_observe(
    state,
    run,
    capture,
    valid,
    grab_error,
    frame,
    gate_tick,
    observed,
    pre_copy_tick=None,
    copy_error=False,
    queue_error=False,
    channel=0,
):
    """Model owned-copy attempt/commit, including private diagnostic failures.

    State: lastRun,lastCapture,lastCopyTick,lastFrame,haveCopy,haveFrame.
    Invalid epoch/Grab/chronology/rate/frame skips preserve entire state.
    """
    old_run, old_capture, old_tick, old_frame, have_copy, have_frame = state
    if (
        grab_error
        or not valid
        or run == 0
        or not run <= capture <= observed
        or not 0 <= channel <= MASK32
    ):
        return state, False
    same_run = run == old_run
    same_capture = capture == old_capture
    due = not same_run or not have_copy or ((gate_tick - old_tick) & MASK32) >= 1000
    new_frame = not same_run or not same_capture or not have_frame or frame != old_frame
    if not (due and new_frame):
        return state, False
    if pre_copy_tick is None:
        pre_copy_tick = gate_tick
    # Both diagnostic errors intentionally consume budget on an owned attempt.
    return (run, capture, pre_copy_tick & MASK32, frame & MASK32, True, True), True


class EpochSnapshot:
    """Evaluate bounded graph exported from exact native-saved Epoch bytes."""

    def __init__(self, graph):
        self.graph = graph
        self.sources = {}
        for ends in graph["wires"]:
            for sink in ends[1:]:
                if sink in self.sources:
                    raise ValueError("Multiple source drivers")
                self.sources[sink] = ends[0]

    def invoke(self, state, action, run, channel, setup_ok, now):
        g = self.graph
        p = g["ports"]
        image = object()
        error = (False, 0, "original")
        values = {
            g["state"]["previous"]: state,
            p["action"]: action,
            p["run"]: run,
            p["channel"]: channel,
            p["setup_ok"]: setup_ok,
            p["image"]: image,
            p["error"]: error,
        }
        clocks = []

        def value(uid):
            if uid in values:
                return values[uid]
            if uid in self.sources:
                return value(self.sources[uid])
            if uid in g["constants"]:
                c = g["constants"][uid]
                result = decode_scalar(bytes.fromhex(c["data"]), c["width"])
            elif uid in g["tunnels"]:
                t = g["tunnels"][uid]
                if uid != t["outside"]:
                    result = value(t["outside"])
                else:
                    branch = int(bool(value(t["selector"]))) if t.get("selector") else 0
                    result = value(t["inside"][branch])
            else:
                n = g["term_nodes"][uid]
                kind = n["kind"]
                if kind == "unbundle":
                    result = value(n["input"])[n["field"]]
                elif kind == "bundle":
                    result = tuple(value(t) for t in n["fields"])
                else:
                    op, ports = n["opcode"], n["ports"]
                    if op == 1303:
                        clocks.append(now)
                        result = now
                    elif op == 1102:
                        result = value(ports["2"]) == value(ports["1"])
                    elif op == 1104:
                        result = value(ports["2"]) <= value(ports["1"])
                    elif op == 1105:
                        result = value(ports["2"]) != value(ports["1"])
                    elif op == 1061:
                        result = bool(value(ports["2"])) and bool(value(ports["1"]))
                    elif op == 1064:
                        result = not value(ports["1"])
                    elif op == 1516:
                        result = value(ports["3"] if value(ports["2"]) else ports["1"])
                    else:
                        raise ValueError("Unsupported source opcode")
            values[uid] = result
            return result

        if value(g["state"]["stop"]) != 1:
            raise ValueError("State loop must execute once")
        committed = value(g["state"]["next"])
        reply = (value(p["capture"]), value(p["channel_out"]), bool(value(p["valid"])))
        if value(p["image_out"]) is not image or value(p["error_out"]) is not error:
            raise ValueError("Business image/error identity lost")
        return committed, reply, clocks


class SetupSnapshot(EpochSnapshot):
    """Check native Setup wrapper wiring with an explicit stub Epoch reply."""

    def invoke(self, run, channel, original_error, setup_ok, epoch_reply):
        g, p = self.graph, self.graph["ports"]
        call = g["call_ports"]
        image = object()
        values = {
            p["run"]: run,
            p["channel"]: channel,
            p["error"]: original_error,
            p["image"]: image,
            p["setup_ok"]: setup_ok,
            p["action"]: 0,
            p["frame"]: 0,
            call["2"]: epoch_reply[0],
            call["1"]: epoch_reply[1],
            call["0"]: epoch_reply[2],
        }

        def value(uid):
            if uid in values:
                return values[uid]
            if uid in self.sources:
                return value(self.sources[uid])
            if uid in g["constants"]:
                c = g["constants"][uid]
                result = decode_scalar(bytes.fromhex(c["data"]), c["width"])
            else:
                node = g["term_nodes"][uid]
                if node["kind"] == "unbundle":
                    result = value(node["input"])[node["field"]]
                elif node["opcode"] == 1064:
                    result = not value(node["ports"]["1"])
                else:
                    raise ValueError("Unexpected Setup source node")
            values[uid] = result
            return result

        inputs = tuple(value(call[str(c)]) for c in (11, 10, 9, 8))
        reply = tuple(value(p[r]) for r in ("capture", "channel_out", "valid"))
        if (
            value(p["image_out"]) is not image
            or value(p["error_out"]) is not original_error
        ):
            raise ValueError("Business image/error identity lost")
        return inputs, reply


def _read_pinned(path, snapshot_hash, native_hash, evaluator):
    with open(path, "rb") as stream:
        raw = stream.read()
    if hashlib.sha256(raw).hexdigest() != snapshot_hash:
        raise ValueError("Semantic snapshot checksum mismatch")
    graph = json.loads(raw.decode("utf-8"))
    if graph["provenance"]["native_vi_sha256"] != native_hash:
        raise ValueError("Unexpected native source identity")
    return evaluator(graph)


def read_snapshot(path):
    return _read_pinned(path, SNAPSHOT_SHA256, EPOCH_NATIVE_SHA256, EpochSnapshot)


def read_setup_snapshot(path):
    return _read_pinned(path, SETUP_SNAPSHOT_SHA256, SETUP_NATIVE_SHA256, SetupSnapshot)


def audit_setup(snapshot):
    count = 0
    for run, channel, status, external_setup in itertools.product(
        (0, 100, 200), (0, 3, 4, MASK32), (False, True), (False, True)
    ):
        error = (status, -123 if status else 0, "original source")
        reply = (1234, channel, not status)
        actual = snapshot.invoke(run, channel, error, external_setup, reply)
        if actual != ((1, run, channel, not status), reply):
            raise ValueError("Native Setup source wiring differs from contract")
        count += 1
    return {
        "offline_native_wrapper_wiring_cases": count,
        "Epoch_reply_is_stubbed": True,
        "native_vi_execution_proven": False,
        "hardware_executed": False,
    }


def audit_epoch(snapshot):
    count = 0
    states = (
        (0, 0, 0, False),
        (100, 101, 2, True),
        (100, 101, 2, False),
        (200, 202, 3, True),
    )
    for st, action, run, channel, ok, now in itertools.product(
        states,
        (0, 1, 2, 3, 4, MASK32),
        (0, 99, 100, 200),
        (0, 3, 4, MASK32),
        (False, True),
        (0, 99, 100, 101, 203),
    ):
        actual = snapshot.invoke(st, action, run, channel, ok, now)
        expected = epoch_transition(st, action, run, channel, ok, now)
        if actual[:2] != expected:
            raise ValueError("Native-source graph differs from epoch contract")
        expected_clock = action == 1 and run != 0 and run == st[0] and ok
        if bool(actual[2]) != expected_clock:
            raise ValueError("Source UTC clock appears in wrong lifecycle branch")
        count += 1
    return {
        "offline_native_source_graph_cases": count,
        "native_vi_execution_proven": False,
        "hardware_executed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot")
    parser.add_argument("--kind", choices=("epoch", "setup"), default="epoch")
    args = parser.parse_args()
    result = (
        audit_epoch(read_snapshot(args.snapshot))
        if args.kind == "epoch"
        else audit_setup(read_setup_snapshot(args.snapshot))
    )
    print(json.dumps(result, indent=2))
