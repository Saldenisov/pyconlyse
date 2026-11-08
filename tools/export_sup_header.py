"""Extract native frequency choices only; never publish a frequency command."""

import argparse
import json
import re

from export_sup_live_display_map import OUTPUT, original

HEADER_OUTPUT = OUTPUT.with_name("elyseSupervisionHeader.json")
LABELS = ["0,2 Hz", "0,5 Hz", "1 Hz", "2 Hz", "5 Hz", "10 Hz", "25 Hz", "50 Hz"]
VALUES = [4981000, 1981000, 981000, 481000, 181000, 81000, 21000, 1000]


def build_header(receipt=None, roots=None):
    if roots is None:
        receipt, roots = original()
    controls = roots["fp"].findall(".//*[@class='fPDCO'][@uid='53480']")
    assert len(controls) == 1, "native frequency control identity changed"
    ring = controls[0].find("ddo")
    assert ring.get("class") == "stdRing" and ring.get("uid") == "53463"
    buffers = ring.findall("partsList/*[@class='multiLabel']/buf")
    assert len(buffers) == 1
    labels = re.findall(r'"([^\"]*)"', buffers[0].text)
    values = [int(node.text, 16) for node in ring.findall("ringSparseValues/*")]
    assert labels == LABELS and values == VALUES, "native frequency choices changed"
    return dict(
        schema_version=1,
        source_sha256=receipt["sha256"],
        control_uid="53480",
        choices=[
            dict(label=label, value=value) for label, value in zip(labels, values)
        ],
        telemetry_bank="C1011NI6602",
        telemetry_index=3,
        selection_scope="local_draft_only",
        hardware_writes=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    header = build_header()
    if args.write:
        HEADER_OUTPUT.write_text(
            json.dumps(header, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(header, ensure_ascii=False, indent=2))
