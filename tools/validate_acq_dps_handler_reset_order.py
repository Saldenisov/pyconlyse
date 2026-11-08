"""Validate saved ACQ 23 DPS handler-reset and PSP-publish frame orders.

Usage: python tools/validate_acq_dps_handler_reset_order.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


# Event case: DPS field, containing ordered sequence UID, reset frame,
# publish frame. These are source identities, not runtime acknowledgements.
EXPECTED = {
    3: (0, "18783", 10, 11),
    4: (1, "7929", 5, 6),
    5: (2, "34597", 8, 9),
    6: (3, "26556", 15, 16),
    7: (5, "23281", 2, 3),
    8: (7, "26235", 2, 3),
    9: (9, "30983", 2, 3),
    10: (11, "23507", 3, 4),
    11: (12, "33686", 2, 3),
    12: (4, "38057", 5, 6),
    13: (6, "24303", 6, 7),
    14: (8, "36008", 6, 7),
    15: (10, "40147", 6, 7),
    16: (20, "30036", 13, 14),
    17: (23, "42523", 4, 5),
    18: (13, "34267", 1, 2),
    19: (14, "43701", 1, 2),
    20: (15, "53984", 2, 3),
    21: (17, "31655", 2, 3),
    22: (16, "32863", 2, 3),
    23: (18, "45189", 1, 2),
    24: (19, "40791", 2, 3),
    25: (21, "38798", 3, 4),
}


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    events = unique(root, "eventStruct", "43").find("diagramList")
    require(events is not None and len(events) == 26,
            "ACQ event-frame count changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]
    signal_by_term = {}
    for group in signals:
        for term_uid in group:
            signal_by_term.setdefault(term_uid, []).append(group)
    literal_values = {
        node.get("uid"): node.findtext("dco/ConstValue")
        for node in root.findall(".//*[@class='term']")
    }

    def linked(*term_uids: str) -> bool:
        return any(set(term_uids) <= group
                   for group in signal_by_term.get(term_uids[0], ()))

    def dps_local(node, writer: bool) -> bool:
        return (node.get("class") == "gRef"
                and node.findtext("termList/*/dco/paramIdx") == "36"
                and node.find("termList/*").findtext("objFlags")
                == ("36864" if writer else "4096"))

    require(set(EXPECTED) == set(range(3, 26))
            and {row[0] for row in EXPECTED.values()}
            == set(range(22)) | {23},
            "expected implemented DPS event/field set changed")
    for case_index, (dps_index, sequence_uid, reset_frame, publish_frame) in EXPECTED.items():
        event = events[case_index]
        reset_candidates = []
        for writer in event.iter():
            if not dps_local(writer, True):
                continue
            writer_term = writer.find("termList/*").get("uid")
            for mux in event.iter():
                if mux.get("class") != "nMux":
                    continue
                terms = mux.findall("termList/*")
                if len(terms) != 3 or not linked(writer_term, terms[0].get("uid")):
                    continue
                field_term = terms[2].get("uid")
                if field(mux, field_term) != dps_index:
                    continue
                false_sources = [term_uid for term_uid, value in literal_values.items()
                                 if value == "0000" and linked(term_uid, field_term)]
                if len(false_sources) != 1:
                    continue
                if not any(dps_local(reader, False)
                           and linked(reader.find("termList/*").get("uid"),
                                      terms[1].get("uid"))
                           for reader in event.iter()):
                    continue
                reset_candidates.append((writer, mux))
        require(len(reset_candidates) == 1,
                f"event {case_index} DPS[{dps_index}] local reset changed")
        reset_writer, _ = reset_candidates[0]

        publish_candidates = []
        for psp_writer in event.iter():
            if psp_writer.get("class") != "sharedVariableDynamicWrite":
                continue
            writer_terms = {term.get("uid")
                            for term in psp_writer.findall("termList/*")}
            has_dps_payload = any(
                dps_local(reader, False)
                and any(linked(reader.find("termList/*").get("uid"), term_uid)
                        for term_uid in writer_terms)
                for reader in event.iter()
            )
            has_dps_uri = any(
                value is not None and value.endswith("2F445053")
                and any(linked(literal_uid, term_uid) for term_uid in writer_terms)
                for literal_uid, value in literal_values.items()
            )
            if has_dps_payload and has_dps_uri:
                publish_candidates.append(psp_writer)
        require(len(publish_candidates) == 1,
                f"event {case_index} DPS PSP writer changed")
        psp_writer = publish_candidates[0]
        sequence = unique(root, "sequence", sequence_uid)
        frames = sequence.find("diagramList")
        require(sequence in event.iter()
                and frames is not None
                and reset_frame + 1 == publish_frame
                and reset_writer in frames[reset_frame].iter()
                and psp_writer in frames[publish_frame].iter(),
                f"event {case_index} DPS reset/publish ordering changed")
    return [
        "Each ACQ event 3..25 resets exactly its own implemented DPS field "
        "to False in a local cluster, then attempts a DPS PSP write in "
        "the next ordered frame; DPS[22] has no event handler",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ DPS handler reset and next-frame publication")


if __name__ == "__main__":
    main()
