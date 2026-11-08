"""Audit every write-side ACQ EPS local reference in the saved root VI.

Usage: python tools/validate_acq_eps_local_writer_coverage.py SOURCE_EXPORT_ZIP
Read-only: no VI, PSP variable, or hardware is accessed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from validate_acq_modulator_start_event_guards import checked_root, require, unique


EXPECTED_FIELD_8_WRITERS = {
    "18625": "01",    # event 3 cooling start
    "35487": "01",    # event 5 General Modulator start
    "28738": "0000",  # event 6 General Modulator stop
}


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    owners = {}
    for node in root.iter():
        if node.get("class") in (None, "signal"):
            continue
        for term in node.findall("termList/*"):
            if term.get("class") == "term":
                uid = term.get("uid")
                require(uid not in owners, f"duplicate terminal UID {uid}")
                owners[uid] = (node, term)

    links = defaultdict(list)
    for signal in root.findall(".//*[@class='signal']"):
        terms = [term.get("uid") for term in signal.findall("termList/*")]
        for uid in terms:
            links[uid].extend(peer for peer in terms if peer != uid)

    writers = [
        ref for ref in root.findall(".//*[@class='gRef']")
        if ref.findtext("termList/*/dco/paramIdx") == "44"
        and int(ref.findtext("termList/*/objFlags", default="0")) & 0x8000
    ]
    require(len(writers) == 27, f"EPS local writer count changed: {len(writers)}")
    upstream = {}
    for ref in writers:
        uid = ref.find("termList/*").get("uid")
        peer_ids = links.get(uid, [])
        require(len(peer_ids) == 1, f"EPS writer {ref.get('uid')} fan-in changed")
        node, term = owners[peer_ids[0]]
        upstream[ref.get("uid")] = (node, term)

    muxes = {
        node.get("uid"): node
        for node, _ in upstream.values() if node.get("class") == "nMux"
    }
    require(len(muxes) == 25, f"fieldwise EPS writer count changed: {len(muxes)}")
    require({uid for uid, (node, _) in upstream.items()
             if node.get("class") != "nMux"} == {"30267", "18021"},
            "whole-cluster EPS writer set changed")

    source, term = upstream["30267"]
    require(source.get("class") == "sRN" and source.get("uid") == "33056"
            and term.get("uid") == "25379"
            and term.findtext("dco/ConstValue") == "00" * 78,
            "startup whole-cluster EPS zero initializer changed")

    read, term = upstream["18021"]
    require(read.get("class") == "sharedVariableDynamicRead"
            and read.get("uid") == "19997" and term.get("uid") == "20015",
            "Timeout whole-cluster EPS PSP read changed")
    uri_term = unique(root, "sRN", "10119").find("termList/*[@uid='20078']")
    require(uri_term is not None
            and bytes.fromhex(uri_term.findtext("dco/ConstValue", default="")[8:]).decode("ascii")
            == "ni.var.psp://10.20.30.2/SUPERVISION/EPS"
            and "19999" in links["20078"], "EPS read URI wire changed")
    event = unique(root, "eventStruct", "43").find("diagramList")[0]
    require(event.get("uid") == "53" and read in event.iter(),
            "EPS whole-cluster read moved from Timeout event")
    timeout_sequence = unique(root, "sequence", "10111")
    timeout_frame_0 = timeout_sequence.find("diagramList")[0]
    require(timeout_sequence in event.iter()
            and timeout_frame_0.get("uid") == "10115"
            and read in timeout_frame_0.iter(),
            "EPS whole-cluster read moved from Timeout frame 0")

    field_8_writers = {}
    for mux_uid, mux in muxes.items():
        field_terms = [
            term for term in mux.findall("termList/*")
            if term.findtext("dco/i") == "8"
            and int(term.findtext("objFlags", default="0")) & 0x8000
            and not int(term.findtext("objFlags", default="0")) & 0x20000
        ]
        if not field_terms:
            continue
        require(len(field_terms) == 1,
                f"EPS field 8 appears more than once in mux {mux_uid}")
        peers = links.get(field_terms[0].get("uid"), [])
        sources = [(node, term) for node, term in (owners[uid] for uid in peers)
                   if node.get("class") == "sRN"]
        require(len(sources) == 1,
                f"EPS field 8 literal source fan-in changed in {mux_uid}")
        source, term = sources[0]
        field_8_writers[mux_uid] = term.findtext("dco/ConstValue")
    require(field_8_writers == EXPECTED_FIELD_8_WRITERS,
            f"EPS field 8 direct writer set changed: {field_8_writers}")
    runtime_frames = unique(root, "eventStruct", "43").find("diagramList")
    for event_index, mux_uid in ((3, "18625"), (5, "35487"), (6, "28738")):
        require(muxes[mux_uid] in runtime_frames[event_index].iter(),
                f"EPS[8] bundle {mux_uid} moved from event {event_index}")
    return [
        "27 write-side EPS local references: 25 fieldwise bundles, "
        "one zero-valued cluster initializer, one remote whole-cluster PSP read",
        "Only three fieldwise EPS[8] writers: event 3 True, event 5 True, "
        "event 6 False; Timeout can replace the entire EPS cluster",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ EPS local writer coverage")


if __name__ == "__main__":
    main()
