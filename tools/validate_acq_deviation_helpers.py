"""Independent XML wire proof for the original Acquisition deviation helpers.

No LabVIEW, lvkit, NI, PSP, network, or hardware imports. Existing native
screenshots corroborate this topology but belong to Supervision copies;
they are not claimed to be new hash-matched Acquisition screenshots.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

ARCHIVE_SHA256 = "645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F"
PROFILES = {
    "direct": {
        "member": "2_SUP_Ecart_lu_ecr_VDirecte.vi",
        "sha256": "5C9E6C4E20FB9CC5B023C9DC56DC58C4D17EB4C63504722A0D6B8D19CF499AD5",
        "input": "1304",
        "output": "2985",
        "channels": 11,
        "locals": {"5927": "2985", "3800": "2985", "1336": "2985"},
    },
    "deviated": {
        "member": "2_SUP_Ecart_lu_ecr_VDéviée.vi",
        "sha256": "80B5B1F9BD5802093D8898A2965BA36E252B9E191F87253AAF531AB3B98AC63F",
        "input": "4245",
        "output": "5285",
        "channels": 9,
        "locals": {"5927": "5285", "3800": "5285", "1336": "5285"},
    },
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def unique(root, kind, uid):
    found = [n for n in root.iter() if n.get("class") == kind and n.get("uid") == uid]
    require(len(found) == 1, f"unique {kind} UID {uid} required")
    return found[0]


def validate_tree(root, profile):
    count = profile["channels"]
    diagrams = [n for n in root.iter() if n.get("class") == "diag"]
    require(
        [d.get("uid") for d in diagrams] == ["3", "5910", "5053"],
        "three diagram identities/order changed",
    )
    sequence = unique(root, "sequence", "2636")
    require(
        [d.get("uid") for d in sequence.findall("diagramList/*")] == ["5910", "5053"],
        "sequence order changed",
    )
    refs = [n for n in root.iter() if n.get("class") == "gRef"]
    require(
        {n.get("uid") for n in refs} == set(profile["locals"]), "local census changed"
    )
    for node in refs:
        require(
            node.findtext("termList/*/dco/paramIdx") == "2", "local bank index changed"
        )
        flags = int(node.findtext("termList/*/objFlags") or "0")
        require(
            bool(flags & 32768) == (node.get("uid") != "1336"),
            "local read/write direction changed",
        )
    frame0, frame1 = diagrams[1:]
    groups0 = [
        set(t.get("uid") for t in s.findall("termList/*"))
        for s in frame0.findall("signalList/*")
    ]
    require(
        any({"5920", "5934"} <= g for g in groups0),
        "frame 0 input-copy/local-write wire changed",
    )
    groups = [
        set(t.get("uid") for t in s.findall("termList/*"))
        for s in frame1.findall("signalList/*")
    ]

    def wired(a, b):
        return any({a, b} <= g for g in groups)

    unbundle = unique(root, "nMux", "2568")
    bundle = unique(root, "nMux", "1555")
    read_terms, write_terms = (
        unbundle.findall("termList/*"),
        bundle.findall("termList/*"),
    )
    require(
        len(read_terms) == 1 + 2 * count and len(write_terms) == 2 + count,
        "cluster lane count changed",
    )
    require(
        [int(t.findtext("dco/i")) for t in read_terms[1:]]
        == [12 * i + j for i in range(count) for j in (6, 7)],
        "consigne/readback nested indices changed",
    )
    require(
        [int(t.findtext("dco/i")) for t in write_terms[2:]]
        == [12 * i + 3 for i in range(count)],
        "orange nested indices changed",
    )
    require(
        wired("1369", write_terms[1].get("uid"))
        and wired(write_terms[0].get("uid"), "3813"),
        "read-modify-write local wiring changed",
    )
    primitives = [n for n in root.iter() if n.get("class") == "prim"]
    require(
        len(primitives) == 3 * count, "arithmetic/comparator operation count changed"
    )
    require(
        sorted(int(n.findtext("primResID")) for n in primitives)
        == sorted([1051, 1054, 1110] * count),
        "primitive opcode census changed",
    )

    def next_node(source, opcode):
        candidates = []
        for n in primitives:
            terms = n.findall("termList/*")
            if n.findtext("primResID") == str(opcode) and any(
                wired(source, t.get("uid")) for t in terms[1:]
            ):
                candidates.append(n)
        require(len(candidates) == 1, f"wire {source} -> opcode {opcode} not unique")
        return candidates[0]

    receipts = []
    thresholds = set()
    for i in range(count):
        command, readback = (t.get("uid") for t in read_terms[1 + 2 * i : 3 + 2 * i])
        subtract = next_node(command, 1051)
        sub = subtract.findall("termList/*")
        require(
            wired(command, sub[2].get("uid")) and wired(readback, sub[1].get("uid")),
            "subtraction upper/lower operand wires changed",
        )
        require(
            wired(readback, sub[1].get("uid")) or wired(readback, sub[2].get("uid")),
            "readback is not second subtraction operand",
        )
        require(
            not wired(command, readback),
            "consigne and readback unexpectedly share one wire",
        )
        absolute = next_node(sub[0].get("uid"), 1054)
        absolute_out = absolute.find("termList/*").get("uid")
        greater = next_node(absolute_out, 1110)
        greater_terms = greater.findall("termList/*")
        require(
            wired(absolute_out, greater_terms[2].get("uid")),
            "strict-greater comparison upper operand reversed",
        )
        thresholds.add(
            next(
                t.get("uid")
                for t in sequence.findall(".//*[@class='term']")
                if wired(t.get("uid"), greater_terms[1].get("uid"))
            )
        )
        target = write_terms[2 + i].get("uid")
        if profile["channels"] == 11 and i == 2:
            constants = [
                n
                for n in frame1.findall("nodeList/*")
                if n.find("termList/*/dco/ConstValue") is not None
            ]
            false_terms = [
                t.get("uid")
                for n in constants
                for t in n.findall("termList/*")
                if t.findtext("dco/ConstValue") == "0000"
            ]
            require(
                len(false_terms) == 1 and wired(false_terms[0], target),
                "Phase HF/Laser orange is not literal False",
            )
            require(
                not wired(greater_terms[0].get("uid"), target),
                "Phase comparator unexpectedly drives orange",
            )
        else:
            require(
                wired(greater_terms[0].get("uid"), target),
                "comparator does not drive matching orange lane",
            )
        receipts.append(
            {
                "channel_index": i,
                "subtract": subtract.get("uid"),
                "absolute": absolute.get("uid"),
                "greater": greater.get("uid"),
                "orange_flat_index": 12 * i + 3,
            }
        )
    require(len(thresholds) == 1, "comparators do not share one threshold tunnel")
    return receipts


def checked_roots(archive: Path):
    require(
        hashlib.sha256(archive.read_bytes()).hexdigest().upper() == ARCHIVE_SHA256,
        "original archive SHA256 changed",
    )
    with ZipFile(archive) as zipped:
        return {
            name: ET.fromstring(zipped.read(p["member"] + "/vi_BDHb.xml"))
            for name, p in PROFILES.items()
        }
