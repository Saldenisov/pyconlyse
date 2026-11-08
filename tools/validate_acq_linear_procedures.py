"""Decode complete direct graphs of simple ACQ procedure sequences, offline.

Every operation and direct net must have a supported role. Only explicitly
qualified nested loops/cells are accepted; whole Acquisition remains open.
"""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from DeviceServers.control.elyse_acq.vi_simulation.procedure_sequences import PROCEDURES
from validate_acq_counter_procedures import COUNTER_FRAMES, validate_counter_frame
from validate_acq_event_envelopes import ROWS, validate_envelopes
from validate_acq_magnet_conditioning import validate_ramp
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_vam_status import checked_vam

EVENTS = tuple(range(3, 26))
BANK_TYPES = {
    9: ("C6NI6703", 10, "NumFloat64"),
    10: ("C7NI6703", 10, "NumFloat64"),
    15: ("C4_OUT_DIO96", 32, "Boolean"),
    17: ("C3_OUT_DIO96", 40, "Boolean"),
    36: ("DPS", 29, "Boolean"),
    44: ("EPS", 77, "Boolean"),
}


def decode_frame(
    root,
    metadata,
    frame,
    duration_port,
    duration_ms,
    names,
    *,
    bank_types=None,
    scalar_types=None,
    dbl_values=(0.0,),
):
    """Return unordered same-frame effects; reject every unexplained net/node."""
    if frame.get("uid") in COUNTER_FRAMES:
        return validate_counter_frame(root, metadata, frame)
    bank_types = BANK_TYPES if bank_types is None else bank_types
    scalar_types = {35: ("Boolean", "ACTION")} if scalar_types is None else scalar_types
    nodes = {n.get("uid"): n for n in frame.findall("zPlaneList/*[@class]")}
    literals = {
        t.get("uid"): t
        for t in frame.findall("nodeList/*/termList/*")
        if t.find("dco/ConstValue") is not None
    }
    placeholders = [
        n.get("uid") for n in frame.findall("zPlaneList/*") if n.get("class") is None
    ]
    require(
        set(placeholders) == set(literals) and len(placeholders) == len(literals),
        "literal operation/container mismatch",
    )
    nets = [
        frozenset(t.get("uid") for t in s.findall("termList/*"))
        for s in frame.findall("signalList/*")
    ]
    require(len(set(nets)) == len(nets), "duplicate net")
    used_nets, used_nodes, used_literals = {}, set(), set()
    effects = []

    def net(port):
        matches = [n for n in nets if port in n]
        require(len(matches) == 1, f"port {port} has no unique direct net")
        return matches[0]

    def connect(*ports):
        actual = net(ports[0])
        require(frozenset(ports) <= actual, f"unexpected wire at {ports}")
        used_nets.setdefault(actual, set()).update(ports)

    def peer(port):
        actual = net(port)
        candidates = actual - {port}
        if len(candidates) > 1:
            candidates &= set(literals)
        require(len(candidates) == 1, f"ambiguous peer at {port}")
        return next(iter(candidates))

    def td(term):
        ident = term.findtext("dco/typeDesc")
        require(ident and ident.startswith("TypeID("), "missing saved type")
        return heap_type(metadata, int(ident[7:-1]))[0]

    def literal(port, typ):
        require(
            port in literals and td(literals[port]).get("Type") == typ,
            f"literal {port} has unexpected type",
        )
        used_literals.add(port)
        raw = bytes.fromhex(literals[port].findtext("dco/ConstValue"))
        if typ == "Boolean":
            require(raw in (b"\x01", b"\x00\x00"), "unsupported Boolean encoding")
            return raw == b"\x01"
        if typ == "NumUInt32":
            require(len(raw) == 4, "invalid U32 literal")
            return int.from_bytes(raw, "big")
        if typ == "NumFloat64":
            require(len(raw) == 8 or raw == bytes(9), "invalid saved DBL encoding")
            value = 0.0 if raw == bytes(9) else struct.unpack(">d", raw)[0]
            require(
                math.isfinite(value) and value in dbl_values,
                "DBL literal outside qualified values",
            )
            return value
        require(typ == "Refnum", "unsupported literal")
        desc = td(literals[port])
        require(
            desc.get("Ident") == "Variable"
            and len(raw) >= 4
            and int.from_bytes(raw[:4], "big") == len(raw) - 4,
            "invalid shared-variable URI literal",
        )
        return raw[4:].decode("ascii")

    locals_by_port = {}
    for uid, node in nodes.items():
        if node.get("class") == "label":
            used_nodes.add(uid)
        if node.get("class") != "gRef":
            continue
        terms = node.findall("termList/*")
        require(len(terms) == 1, "unexpected local connector")
        term = terms[0]
        locals_by_port[term.get("uid")] = (
            uid,
            int(term.findtext("dco/paramIdx")),
            bool(int(term.findtext("dco/objFlags", "0")) & 1),
            term,
        )

    def local(port, read):
        require(port in locals_by_port, f"no local at {port}")
        uid, bank, direction, term = locals_by_port[port]
        require(direction == read, "local direction mismatch")
        desc = td(term)
        if bank in scalar_types:
            kind, label = scalar_types[bank]
            require(
                desc.get("Type") == kind and desc.get("Label") == label,
                "scalar saved type changed",
            )
        else:
            require(bank in bank_types, "unsupported bank")
            label, count, kind = bank_types[bank]
            flat = metadata.find("VCTP/Section").findall("TypeDesc")
            members = desc.findall("TypeDesc")
            require(
                desc.get("Type") == "Cluster"
                and desc.get("Label") == label
                and len(members) == count
                and all(
                    flat[int(c.get("TypeID"))].get("Type") == kind for c in members
                ),
                "saved local bank shape changed",
            )
        used_nodes.add(uid)
        return bank, term

    for uid, node in nodes.items():
        if node.get("class") != "nMux":
            continue
        used_nodes.add(uid)
        terms = node.findall("termList/*")
        require(len(terms) >= 3, "empty bundle update")
        output, base = (terms[i].get("uid") for i in (0, 1))
        write_port, read_port = peer(output), peer(base)
        bank, write_term = local(write_port, False)
        read_bank, read_term = local(read_port, True)
        require(bank == read_bank, "bundle base/output bank mismatch")
        read_type, write_type = td(read_term), td(write_term)
        require(
            read_type.get("Type") == write_type.get("Type") == "Cluster",
            "bundle local is not cluster",
        )
        flat = metadata.find("VCTP/Section").findall("TypeDesc")
        children = [flat[int(c.get("TypeID"))] for c in read_type.findall("TypeDesc")]
        require(
            [c.get("Type") for c in children]
            == [
                flat[int(c.get("TypeID"))].get("Type")
                for c in write_type.findall("TypeDesc")
            ],
            "local cluster type mismatch",
        )
        connect(output, write_port)
        connect(base, read_port)
        changes = []
        for term in terms[2:]:
            index = int(term.findtext("dco/i", "0"))
            kind = td(term).get("Type")
            require(
                0 <= index < len(children)
                and children[index].get("Type") == kind
                and kind in ("Boolean", "NumFloat64"),
                "unsupported bundle field",
            )
            const_port = peer(term.get("uid"))
            value = literal(const_port, kind)
            connect(term.get("uid"), const_port)
            changes.append((index, value))
        require(
            len({i for i, _ in changes}) == len(changes), "duplicate field assignment"
        )
        effects.append(("write", bank, tuple(sorted(changes))))

    for uid, node in nodes.items():
        if node.get("class") == "forLoop":
            effects.append(validate_ramp(root, metadata, frame))
            used_nodes.add(uid)
            used_literals.update(literals)
            used_nets.update({n: set(n) for n in nets})
        if node.get("class") == "flatSequence":
            require(
                not node.findall("termList/*") and not node.findall("tunnelList/*"),
                "flat sequence has external tunnel",
            )
            cells = node.findall("sequenceList/*/diagramList/*")
            require(2 <= len(cells) <= 3, "unsupported focal flat cell count")
            effects.append(
                (
                    "subsequence",
                    tuple(
                        (
                            cell.get("uid"),
                            decode_frame(
                                root,
                                metadata,
                                cell,
                                None,
                                None,
                                names,
                                bank_types=bank_types,
                                scalar_types=scalar_types,
                                dbl_values=dbl_values,
                            ),
                        )
                        for cell in cells
                    ),
                )
            )
            used_nodes.add(uid)
        if node.get("class") == "prim":
            require(node.findtext("primResID") == "1302", "unsupported primitive")
            terms = node.findall("termList/*")
            require(
                len(terms) == 2 and terms[1].findtext("dco/objFlags") == "65536",
                "wait ports changed",
            )
            port = terms[1].get("uid")
            source = peer(port)
            ms = (
                duration_ms if source == duration_port else literal(source, "NumUInt32")
            )
            connect(source, port)
            require(not any(terms[0].get("uid") in n for n in nets), "wait output used")
            used_nodes.add(uid)
            effects.append(("wait", ms))
        if node.get("class") == "gRef" and uid not in used_nodes:
            term = node.find("termList/*")
            port = term.get("uid")
            if not (int(term.findtext("dco/objFlags", "0")) & 1):
                bank, _ = local(port, False)
                require(bank in scalar_types, "unsupported direct local write")
                source = peer(port)
                value = literal(source, scalar_types[bank][0])
                connect(source, port)
                effects.append(("write", bank, ((-1, value),)))

    publications, handlers = {}, {}
    focal_calls, clear_calls = {}, {}
    for uid, node in nodes.items():
        if node.get("class") == "sharedVariableDynamicWrite":
            terms = node.findall("termList/*")
            require(
                len(terms) == 5
                and [t.findtext("dco/terminal_ID", "") for t in terms]
                == ["0B", "03", "08", "", "0A"]
                and [t.findtext("dco/objFlags") for t in terms]
                == ["128", "513", "512", "513", "128"],
                "PSP connector changed",
            )
            ports = [t.get("uid") for t in terms]
            uri_port, data_port = peer(ports[0]), peer(ports[4])
            uri = literal(uri_port, "Refnum")
            prefix = "ni.var.psp://10.20.30.2/SUPERVISION/"
            require(uri.startswith(prefix), "PSP destination changed")
            bank, _ = local(data_port, True)
            connect(uri_port, ports[0])
            connect(data_port, ports[4])
            require(not any(ports[1] in n for n in nets), "PSP URL output used")
            publications[uid] = (uri[len(prefix) :], bank, ports[2], ports[3])
            used_nodes.add(uid)
        if node.get("class") == "iUse":
            name = names.get(uid)
            terms = node.findall("termList/*")
            if name in ("1_Focales ON.vi", "1_Focales OFF.vi", "Clear Errors.vi"):
                count = 8 if name == "Clear Errors.vi" else 7
                active_slot = 4 if count == 8 else 0
                require(
                    len(terms) == count
                    and [int(t.findtext("dco/paramIdx", "0")) for t in terms]
                    == list(range(count)),
                    "focal/clear connector changed",
                )
                require(
                    all(
                        not any(t.get("uid") in n for n in nets)
                        for slot, t in enumerate(terms)
                        if slot != active_slot
                    ),
                    "unexpected focal/clear wired port",
                )
                require(
                    terms[active_slot].findtext("dco/objFlags")
                    == ("512" if count == 8 else "513"),
                    "focal/clear error direction changed",
                )
                if count == 8:
                    clear_calls[uid] = terms[4].get("uid")
                else:
                    focal_calls[uid] = (name, terms[0].get("uid"))
                used_nodes.add(uid)
                continue
            require(name == "Simple Error Handler.vi", "unsupported subVI")
            require(
                len(terms) == 10
                and [int(t.findtext("dco/paramIdx", "0")) for t in terms]
                == list(range(10)),
                "Simple Error Handler connector changed",
            )
            require(
                all(not any(t.get("uid") in n for n in nets) for t in terms[:9]),
                "non-default error-handler connector used",
            )
            require(
                terms[9].findtext("dco/objFlags") == "512",
                "handler error input changed",
            )
            handlers[uid] = terms[9].get("uid")
            used_nodes.add(uid)
    if focal_calls or clear_calls:
        require(
            len(focal_calls) == 1
            and len(clear_calls) + len(handlers) == 1
            and not publications,
            "unsupported focal error graph",
        )
        name, output = next(iter(focal_calls.values()))
        destination = clear_calls if clear_calls else handlers
        connect(output, next(iter(destination.values())))
        effects.append(
            ("call_clear_error" if clear_calls else "call_handle_error", name)
        )
    if publications:
        require(len(handlers) == 1, "PSP chain must end at exactly one error handler")
        remaining = dict(publications)
        starts = [
            uid for uid, row in remaining.items() if not any(row[2] in n for n in nets)
        ]
        require(len(starts) == 1, "PSP chain initial error is not uniquely unwired")
        current = starts[0]
        chain = []
        while current in remaining:
            name, bank, error_in, error_out = remaining.pop(current)
            chain.append((name, bank))
            next_port = peer(error_out)
            connect(error_out, next_port)
            candidates = [uid for uid, row in remaining.items() if row[2] == next_port]
            if candidates:
                require(len(candidates) == 1, "ambiguous PSP error continuation")
                current = candidates[0]
            else:
                require(
                    next_port == next(iter(handlers.values())) and not remaining,
                    "PSP error chain not complete",
                )
                break
        effects.append(("publish", tuple(chain)))
    else:
        require(not handlers or focal_calls, "standalone error handler unsupported")
    require(used_nodes == set(nodes), f"unexplained operations in {frame.get('uid')}")
    require(used_literals == set(literals), f"unused literals in {frame.get('uid')}")
    require(
        set(used_nets) == set(nets)
        and all(set(n) == ports for n, ports in used_nets.items()),
        f"unexplained nets/fanout in {frame.get('uid')}",
    )
    return tuple(sorted(effects, key=repr))


def decode_tree(root, metadata):
    names = call_names(metadata)
    result = {}
    for event in EVENTS:
        row = ROWS[event - 3]
        sequence = unique(root, "sequence", row[12])
        frames = sequence.findall("diagramList/*")
        ports = sequence.findall("termList/*")
        require(
            len(ports) == 1
            and ports[0].get("uid") == row[13]
            and ports[0].findtext("dco/objFlags") in ("10240", "2048"),
            "duration tunnel changed",
        )
        internal = [t.get("uid") for t in ports[0].findall("dco/termList/*")]
        require(
            len(internal) == len(frames) + 1 and internal[-1] == row[13],
            "sequence tunnel frame mapping changed",
        )
        result[event] = tuple(
            (
                frame.get("uid"),
                decode_frame(
                    root,
                    metadata,
                    frame,
                    internal[index],
                    1000 if event == 3 else 150,
                    names,
                ),
            )
            for index, frame in enumerate(frames)
        )
    return result


def validate_tree(root, metadata):
    validate_envelopes(root, metadata)
    actual = decode_tree(root, metadata)
    require(actual == dict(PROCEDURES), "reviewed procedure sequence/profile changed")
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    root, metadata = checked_vam(args.source_export_zip)
    rows = validate_tree(root, metadata)
    print(
        f"PASS: {len(rows)} procedure paths; "
        f"{sum(len(frames) for frames in rows.values())} stacked frames; "
        "seven nested focal cells; four For and two While bodies; "
        "complete direct nets and typed assignments"
    )
    print("Not full Acquisition coverage; no hardware access or VI execution")


if __name__ == "__main__":
    main()
