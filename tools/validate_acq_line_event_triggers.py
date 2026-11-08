"""Bounded read-only audit of Acquisition beam-line event trigger nodes.

Usage: python tools/validate_acq_line_event_triggers.py PATH_TO_0_ACQ_ELYSE_BDHb.xml
This does not rule out external VI Server clients or deployed-source drift.
"""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


EXPECTED_SHA256 = "36E2857BF3031A1C7AB5A5BE9C8A0C2FADEB91E32D60A29652F536F7F3DDB5CB"
LINE_CASES = ((1, "1660"), (2, "16917"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate(path: Path) -> list[str]:
    require(path.is_file(), f"BDHb XML not found: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    require(digest == EXPECTED_SHA256, f"unexpected BDHb SHA-256: {digest}")
    root = ET.parse(path).getroot()
    event = root.find(".//*[@class='eventStruct'][@uid='43']")
    require(event is not None, "runtime Event Structure 43 absent")
    specs = event.find("EventNodeEvents")
    require(specs is not None and len(specs) == 26, "expected 26 runtime event specifications")
    event_frames = event.find("diagramList")
    require(event_frames is not None and len(event_frames) == 26, "expected 26 event diagrams")

    signaling = []
    for prop in root.findall(".//*[@class='propNode']"):
        names = [(item.text or "").strip('"') for item in prop.findall("termList/*/dco/propList/*/PropItemName")]
        if "Val(Sgnl)" in names:
            ddo = prop.find("ddo")
            signaling.append((prop.get("uid", ""), ddo.get("uid", "") if ddo is not None else ""))
    require(len(signaling) == 24, f"expected 24 Val(Sgnl) nodes, got {len(signaling)}")
    require(all(target not in {"1660", "16917"} for _, target in signaling),
            "beam-line control has an explicit Val(Sgnl) writer")

    results = []
    for case, ddo_uid in LINE_CASES:
        matching_specs = [
            spec for spec in specs
            if spec.findtext("diagramIdx") == str(case) and spec.findtext("ddoUID") == ddo_uid
        ]
        require(len(matching_specs) == 1, f"event {case} registration does not target {ddo_uid}")
        direct_refs = [
            ref for ref in root.findall(".//*[@class='ctlRefConst']")
            if (ref.find("ddo") is not None and ref.find("ddo").get("uid") == ddo_uid)
        ]
        require(len(direct_refs) == 1, f"expected one local control reference to {ddo_uid}")
        require(direct_refs[0] in event_frames[case].iter(),
                f"control reference {ddo_uid} is not confined to its own event case")
        results.append(f"event {case}: Value Change target {ddo_uid}; no root Val(Sgnl) writer")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    args = parser.parse_args()
    for line in validate(args.bdhb_xml):
        print(line)
    print("PASS: no explicit beam-line Val(Sgnl) writer in saved ACQ root VI")


if __name__ == "__main__":
    main()
