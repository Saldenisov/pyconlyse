"""Validate NI6071E initializer's saved controller dataflow, offline only.

Usage: python tools/validate_acq_ni6071e_initializer.py SOURCE_EXPORT_ZIP
Reads hash-pinned XML; never opens LabVIEW, creates a task, or imports NI.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_controlled_stop_wait_tunnels import direct


SOURCE_VI_SHA256 = "FEB881DB3A01B5402D5164C3B149195E83D8A0B089DDAEEA0D6A54D7C4E0F07C"
ARCHIVE_SHA256 = "C150D3978BF6F27602EB5E7AF83E0EFAB1B4D162714F400F28A119E2314C2DD3"
FILE_HASHES = {
    "vi.xml": "9FBC18A17B3914DC1DF7C0ABE3DAE6C8CC0F271AC05024022238683BCE26AFBB",
    "vi_BDHb.xml": "CCBE780CC9DCEAE3F73668D66BF2D3DFE8ECBC8FD640047380AE4156C5C257DD",
    "vi_FPHb.xml": "839B5C2CFDDC2DF4F6A247BE69648D8AF3AB111EC725BAF5A915C51A82ECE6CA",
}

# Connector slot, FP DCO UID, label. Local-reference indices come from CPMp,
# not from connector slot or front-panel serialization order.
CONNECTORS = (
    ("2050", '"Trigger C1 (/1/PFI0)"'),
    ("609", '"Trigger C2 (/2/PFI0)"'),
    ("128", '"Fréquence d\'échantillonnage"'),
    ("580", '"entrée d\'erreur"'),
    ("266", '"échantillons par voie"'),
    ("2322", '"ID C1 DAQmx"'),
    ("645", '"ID C2 DAQmx"'),
    ("1280", '"error out"'),
)


def checked_roots(path: Path) -> dict[str, ET.Element]:
    require(hashlib.sha256(path.read_bytes()).hexdigest().upper() == ARCHIVE_SHA256,
            "unexpected NI6071E source archive SHA-256")
    roots = {}
    with ZipFile(path) as archive:
        require(set(archive.namelist()) == set(FILE_HASHES), "source archive members changed")
        for name, expected in FILE_HASHES.items():
            payload = archive.read(name)
            require(hashlib.sha256(payload).hexdigest().upper() == expected,
                    f"source export hash changed: {name}")
            roots[name] = ET.fromstring(payload)
    return roots


def literal(frame, uid):
    matches = frame.findall(f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue")
    require(len(matches) == 1, f"literal definition {uid} absent or duplicated")
    return matches[0].text


def scalar(frame, uid, expected):
    require(literal(frame, uid) == expected, f"literal {uid} changed")


def doubles(frame, uid):
    payload = bytes.fromhex(literal(frame, uid))
    require(len(payload) >= 4, "range array header absent")
    count = int.from_bytes(payload[:4], "big")
    require(count == 64 and len(payload) == 4 + 8 * count, "range array size changed")
    return struct.unpack(">64d", payload[4:])


def tags(frame, uid):
    payload = bytes.fromhex(literal(frame, uid))
    require(int.from_bytes(payload[:4], "big") == 64, "channel array count changed")
    values, offset = [], 4
    for _ in range(64):
        length = int.from_bytes(payload[offset:offset + 4], "big")
        offset += 4
        values.append(payload[offset:offset + length].decode("ascii"))
        offset += length
    require(offset == len(payload), "channel array length changed")
    return values


def call(root, frame, klass, uid, label, selector=None):
    node = unique(root, klass, uid)
    require(node in frame.findall("zPlaneList/*")
            and node.findtext("label/textRec/text") == f'"{label}"',
            f"initializer call {uid} changed or moved")
    require(all(int(term.findtext("dco/paramIdx", "0")) == index
                for index, term in enumerate(node.findall("termList/*"))),
            f"initializer call {uid} connector slots changed")
    if selector is not None:
        require(node.findtext("instanceSelector/menuInstanceUsed") == selector,
                f"polymorphic selection {uid} changed")
    return node


def validate_trees(roots: dict[str, ET.Element]) -> list[str]:
    main, root, fp = (roots[name] for name in ("vi.xml", "vi_BDHb.xml", "vi_FPHb.xml"))
    require(main.find("LVSR/Section").get("Name") == "1_ACQ_INIT_NI6071E.vi",
            "source VI identity changed")
    pane = fp.find(".//conPane")
    require(pane.findtext("conId") == "4825", "connector pattern changed")
    connections = pane.findall("cons/*/ConnectionDCO")
    require([node.get("uid") for node in connections] == [uid for uid, _ in CONNECTORS],
            "connector assignments changed")
    for uid, label in CONNECTORS:
        control = unique(fp, "fPDCO", uid)
        require(control.findtext("ddo/partsList/*[@class='label']/textRec/text") == label,
                "front-panel control label changed")
    parameter_order = [int(node.get("Flags"), 16) >> 8
                       for node in main.findall("CPMp/Section/TypeDesc")]
    require(parameter_order == [1, 0, 6, 3, 4, 7, 5, 2],
            "connector-to-local parameter map changed")
    # Slot -> local parameter index. This mapping is checked only for this VI.
    local_fp = {parameter: connections[slot].get("uid")
                for slot, parameter in enumerate(parameter_order)}
    require(local_fp == {0: "609", 1: "2050", 2: "1280", 3: "580",
                         4: "266", 5: "645", 6: "128", 7: "2322"},
            "local-to-control mapping changed")

    sequence = unique(root, "sequence", "101")
    frames = sequence.findall("diagramList/*")
    require([frame.get("uid") for frame in frames] == ["1144", "2383", "944"],
            "initializer sequence order changed")
    require({node.get("uid") for node in root.iter() if node.get("class") == "iUse"}
            == {"2629", "2462", "134"}, "initializer ordinary-call set changed")
    require({node.get("uid") for node in root.iter() if node.get("class") == "polyIUse"}
            == {"2818", "2959", "2393", "998", "2454", "2212"},
            "initializer polymorphic-call set changed")
    require({node.get("uid") for node in root.iter() if node.get("class") == "propNode"}
            == {"2561", "2380"}, "initializer property-node set changed")
    require(not any(node.get("class") in {"select", "whileLoop", "eventStruct"}
                    for node in root.iter()), "initializer gained another control branch")

    for (index, task_name, create_uid, timing_uid, trigger_uid, prop_uid,
         references, constants, wires, loop_uid, channel_uid, array_uids, array_ports) in (
        (1, "C1_NI6071E", "2629", "2393", "2454", "2561",
         (("3428", "3439", 1), ("3381", "3390", 6),
          ("3402", "3413", 4), ("3454", "3464", 7)),
         (("3649", "01"), ("3659", "0000000A43315F4E493630373145"),
          ("3638", "00000040"), ("3732", "0000000C4F6E626F617264436C6F636B"),
          ("3693", "000027C2"), ("3719", "00002828"), ("3706", "00002828"),
          ("3680", "000028B9"), ("3670", "01"), ("3539", "0000286C")),
         (("3439", "2476"), ("3390", "2411"), ("3413", "2402"),
          ("3732", "2417"), ("3693", "2399"), ("3719", "2423"),
          ("3706", "2492"), ("2408", "2457"), ("2442", "2525"),
          ("2469", "2566"), ("2549", "2584"), ("2575", "3464"),
          ("3680", "2602"), ("3670", "2620"), ("3649", "2638"),
          ("3659", "2635"), ("3638", "2682"), ("2593", "2390"),
          ("2644", "2694"), ("2677", "2700"),
          ("2686", "2396"), ("2690", "2429"), ("3539", "2737")),
         "2680", "2818", ("842", "1770", "1808"),
         (("1351", "1345", "2859"), ("1431", "1428", "2839"),
          ("1393", "1386", "2833"))),
        (2, "C2_NI6071E", "2462", "998", "2212", "2380",
         (("3310", "3315", 0), ("3289", "3292", 6),
          ("3299", "3303", 4), ("3322", "3326", 5)),
         (("3547", "01"), ("3569", "0000000A43325F4E493630373145"),
          ("3526", "00000040"), ("3755", "0000000C4F6E626F617264436C6F636B"),
          ("3651", "000027C2"), ("3730", "00002828"), ("3684", "00002828"),
          ("3621", "000028B9"), ("3596", "01"), ("3384", "0000286C")),
         (("3315", "2272"), ("3292", "2143"), ("3303", "2118"),
          ("3755", "2154"), ("3651", "2111"), ("3730", "2161"),
          ("3684", "2286"), ("2127", "2215"), ("2194", "2321"),
          ("2247", "2385"), ("2352", "2401"), ("2389", "3326"),
          ("3621", "2419"), ("3596", "2438"), ("3547", "2490"),
          ("3569", "2482"), ("3526", "2610"), ("2410", "2854"),
          ("2507", "2634"), ("2599", "2652"),
          ("2619", "1041"), ("2626", "2174"), ("986", "2568"), ("3384", "2779")),
         "2604", "2959", ("982", "1067", "1913"),
         (("1001", "996", "2987"), ("1620", "1617", "2974"),
          ("1172", "1169", "2968"))),
    ):
        frame = frames[index]
        call(root, frame, "iUse", create_uid, "DAQmx Create Task.vi")
        call(root, frame, "polyIUse", timing_uid, "DAQmx Timing.vi", "02")
        call(root, frame, "polyIUse", trigger_uid, "DAQmx Trigger.vi", "03")
        prop = unique(root, "propNode", prop_uid)
        require(prop.findtext("nodeName") == '"DAQmx - Lire"'
                and [item.text for item in prop.findall(".//PropItemName")]
                == ['"RelativeTo"', '"DémarAuto"'], "Read properties changed")
        for uid, term_uid, parameter in references:
            ref = unique(root, "gRef", uid)
            require(ref in frame.findall("zPlaneList/*")
                    and int(ref.findtext(f"termList/*[@uid='{term_uid}']/dco/paramIdx", "0"))
                    == parameter, "initializer local reference changed")
        for uid, expected in constants:
            scalar(frame, uid, expected)
        for source, destination in wires:
            direct(frame, source, destination)
        channels, minimum, maximum = array_uids
        require(tags(frame, channels) == [f"{index}/ai{i}" for i in range(64)],
                "ordered physical channel array changed")
        expected_max = tuple((0.05 if i == 2 else 1 if i in (3, 4) else 10)
                             if index == 1 else 10 for i in range(64))
        require(doubles(frame, maximum) == expected_max
                and doubles(frame, minimum) == tuple(-value for value in expected_max),
                "per-channel range values changed")
        loop = unique(root, "forLoop", loop_uid)
        require(loop in frame.findall("zPlaneList/*"), "channel loop moved")
        body = loop.find("diagramList")[0]
        require(body.get("uid") == ("2798" if index == 1 else "2948"),
                "AI channel body identity changed")
        call(root, body, "polyIUse", channel_uid, "DAQmx Create Virtual Channel.vi", "02")
        expected_body_wires = (
            (("1428", "2839"), ("1386", "2833"), ("1345", "2859"),
             ("616", "2845"), ("2703", "2915"), ("2740", "2895"),
             ("2697", "2824"), ("2951", "2693"), ("2850", "2689"))
            if index == 1 else
            (("2661", "3019"), ("1617", "2974"), ("1169", "2968"),
             ("996", "2987"), ("840", "2979"), ("2785", "3008"),
             ("2643", "2964"), ("3038", "2631"), ("2982", "2625")))
        require({frozenset(term.get("uid") for term in signal.findall("termList/*"))
                 for signal in body.findall("signalList/*")}
                == {frozenset(pair) for pair in expected_body_wires}
                and len(body.findall("signalList/*")) == 9,
                "channel-loop internal wire graph changed")
        for literal_uid, (outer_port, inner_port, input_port) in zip(array_uids, array_ports):
            direct(frame, literal_uid, outer_port)
            tunnel = loop.find(f"termList/*[@uid='{outer_port}']/dco")
            require(tunnel.get("class") == "lpTun"
                    and tunnel.findtext("TunnelType") == "01"
                    and [term.get("uid") for term in tunnel.findall("termList/*")]
                    == [inner_port, outer_port], "channel auto-index tunnel changed")
            direct(body, inner_port, input_port)
        error_entry, input_port, output_port, error_exit, rse_uid, rse_port = (
            ("2703", "2915", "2951", "2693", "616", "2845") if index == 1
            else ("2661", "3019", "3038", "2631", "840", "2979"))
        direct(body, error_entry, input_port)
        direct(body, output_port, error_exit)
        scalar(body, rse_uid, "00002763")
        direct(body, rse_uid, rse_port)
        units_outer, units_inner = ("2737", "2740") if index == 1 else ("2779", "2785")
        units_tunnel = loop.find(f"termList/*[@uid='{units_outer}']/dco")
        require(units_tunnel is not None and units_tunnel.get("class") == "lpTun"
                and units_tunnel.findtext("TunnelType", "00") == "00"
                and [port.get("uid") for port in units_tunnel.findall("termList/*")]
                == [units_inner, units_outer], "AI Volts units tunnel changed")
        require(all(term.find("dco").get("class") in {"lMax", "lpTun"}
                    for term in loop.findall("termList/*")),
                "channel loop gained a shift register")
        error_outputs = [term.find("dco") for term in loop.findall("termList/*")
                         if error_exit in {port.get("uid")
                                           for port in term.findall("dco/termList/*")}]
        require(len(error_outputs) == 1
                and error_outputs[0].findtext("TunnelType", "00") == "00",
                "channel error output is no longer non-indexed")

    local = unique(root, "sLoc", "310")
    require(local in sequence.findall("seqLocDCOList/*")
            and local.findtext("diagDefined") == "01"
            and [term.get("uid") for term in local.findall("termList/*")]
            == ["859", "2390", "986"], "C1-to-C2 error sequence local changed")
    call(root, frames[2], "iUse", "134", "Simple Error Handler.vi")
    error_bank_indices = {str(parameter) for parameter, uid in local_fp.items()
                          if uid in {"580", "1280"}}
    require(not any(node.findtext("termList/*/dco/paramIdx", "0") in error_bank_indices
                    for node in root.iter() if node.get("class") == "gRef"),
            "initializer acquired an error in/out local reference")
    forbidden = {"583", "1282", "2814", "2665"}
    require(not any(term.get("uid") in forbidden for signal in root.iter()
                    if signal.get("class") == "signal" for term in signal.findall("termList/*")),
            "formerly unconnected error terminal acquired a wire")
    require(len(sequence.findall("termList/*")) == 0, "initializer sequence acquired an input tunnel")
    return [
        "Two 64-channel AI tasks: C1 ranges +/-0.05 V at ai2, +/-1 V at "
        "ai3/4, +/-10 V elsewhere; C2 +/-10 V throughout; RSE",
        "Sample Clock uses OnboardClock, finite samples and rising edge; "
        "frequency/count locals feed Timing; separate trigger inputs feed "
        "rising Start Digital Edge, not sample-clock source",
        "Create Task auto cleanup=True; Read.RelativeTo=Current Read "
        "Position and Read.AutoStart=True; no explicit Start Task call",
        "C1 final error reaches C2 Create Task via sequence local 310; "
        "C2 final error reaches Simple Error Handler; public error in/out "
        "and handler error output are unwired with no matching local references",
        "Both channel loops use a shared incoming error and non-indexed "
        "last-iteration error output, not an error shift register. "
        "No successful acquisition or physical cleanup is established",
    ]


def validate(path: Path) -> list[str]:
    return validate_trees(checked_roots(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    for line in validate(parser.parse_args().source_export_zip):
        print(line)
    print("PASS: ACQ NI6071E initializer internal wire contract")


if __name__ == "__main__":
    main()
