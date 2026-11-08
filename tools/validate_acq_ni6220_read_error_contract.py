"""Check NI6220 public errors, read/mean bound and runtime stop boundary.

Offline saved-source proof only. No NI, PSP, VISA or LabVIEW execution.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from validate_acq_final_cleanup import exact_wires, public_term, constant, tag_array
from validate_acq_modulator_start_event_guards import checked_root, require, unique


ALL_MEMBERS_ARCHIVE_SHA256 = "645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F"
FILE_HASHES = {
    "1_ACQ_INIT_NI6220.vi": {
        "vi.xml": "17811E09EBD01CD4B29D771ACDD98ABFC6F00FE568035C46BFD00D7CF96AF44B",
        "vi_BDHb.xml": "0559F62CD8D5DFF32C19ED92CC5477D3EB5D062D66FCCADBF09B73603DD4FF13",
        "vi_FPHb.xml": "5AC89D701A535FC56A3F11A74FCCF0AA24011E49647A92482ED2DCC96420522F",
    },
    "1_ACQ_READ_NI6220.vi": {
        "vi.xml": "1CDFDFF70D63BCD0C2522CB64A81DD234232B20EDD781036640471CF6300899B",
        "vi_BDHb.xml": "561C09FE524A8DDB4BB3471A27632D1A9C742E3F0DA17661F59BD0CDAACC9704",
        "vi_FPHb.xml": "FBC9AA052D831C728366AEBBE1F3DC7D754B24CB62DE7AE4FD64AAC98FAD78D7",
    },
}


def checked_ni6220_roots(path):
    require(hashlib.sha256(path.read_bytes()).hexdigest().upper() == ALL_MEMBERS_ARCHIVE_SHA256,
            "original member archive hash changed")
    result = {}
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 51, "original XML member count changed")
        for member, hashes in FILE_HASHES.items():
            result[member] = {}
            for name, expected in hashes.items():
                payload = archive.read(member + "/" + name)
                require(hashlib.sha256(payload).hexdigest().upper() == expected,
                        f"original NI6220 XML hash changed: {member}/{name}")
                result[member][name] = ET.fromstring(payload)
    return result


def connector_map(fp):
    slot = -1
    result = []
    for c in fp.find(".//conPane/cons"):
        slot = int(c.get("index", slot + 1))
        result.append((slot, c.find("ConnectionDCO").get("uid")))
    return result


def direct(frame, source, target):
    require(any({source, target} <= {t.get("uid") for t in s.findall("termList/*")}
                for s in frame.findall("signalList/*")), f"NI6220 wire {source}->{target} changed")


def validate_initializer_error(roots):
    bd, fp, meta = roots["vi_BDHb.xml"], roots["vi_FPHb.xml"], roots["vi.xml"]
    frame = bd.find("root")
    require(frame.get("uid") == "3", "NI6220 initializer root changed")
    require(connector_map(fp) == [(2, "128"), (3, "580"), (4, "266"), (5, "2322"), (7, "1280")],
            "NI6220 initializer connector mapping changed")
    require([n.get("Flags") for n in meta.findall("CPMp/Section/TypeDesc")]
            == ["-1", "-1", "0x0300", "0x0100", "0x0200", "0x0400", "-1", "0x0000"],
            "NI6220 initializer public-to-local mapping changed")
    refs = bd.findall(".//*[@class='gRef']")
    require({(n.get("uid"), n.findtext("termList/*/dco/paramIdx") or "0") for n in refs}
            == {("2820", "0"), ("3454", "4"), ("3402", "2"), ("3381", "3")},
            "NI6220 initializer local reference census changed")
    require(not any("583" in {t.get("uid") for t in s.findall("termList/*")}
                    for s in bd.findall(".//*[@class='signal']")),
            "NI6220 initializer public error input connected")
    writer = unique(bd, "gRef", "2820")
    require(writer.findtext("termList/*/objFlags") == "36864", "NI6220 error-out local write direction changed")
    direct(frame, "2593", "2832")
    require(not any("2665" in {t.get("uid") for t in s.findall("termList/*")}
                    for s in bd.findall(".//*[@class='signal']")), "NI6220 Create Task error input connected")
    for source, target in (("2677", "2700"), ("2690", "2429"), ("2442", "2525"),
                           ("2549", "2584")):
        direct(frame, source, target)
    loop = unique(bd, "forLoop", "2680")
    require(not loop.findall("termList/*/dco[@class='lSR']")
            and not loop.findall("termList/*/dco[@class='rSR']"),
            "NI6220 channel error shift register added")
    body = loop.find("diagramList")[0]
    direct(body, "2703", "2915")
    direct(body, "2951", "2693")
    return "NI6220 INIT ignores public error-in but assigns final internal error to public error-out through local index 0; unlike NI6071E"


def validate_initializer_configuration(roots):
    bd = roots["vi_BDHb.xml"]
    frame = bd.find("root")
    loop = unique(bd, "forLoop", "2680")
    body = loop.find("diagramList")[0]
    require(len(bd.findall(".//*[@class='diag']")) == 2
            and body.get("uid") == "2798", "NI6220 initializer scope changed")
    require({(n.get("class"), n.get("uid")) for n in frame.findall("zPlaneList/*[@class]")}
            == {("gRef", "2820"), ("prim", "634"), ("gRef", "3454"),
                ("gRef", "3402"), ("gRef", "3381"), ("forLoop", "2680"),
                ("iUse", "2629"), ("propNode", "2561"), ("polyIUse", "2454"),
                ("polyIUse", "2393")}, "NI6220 initializer operation census changed")
    require([(n.get("class"), n.get("uid")) for n in body.findall("zPlaneList/*[@class]")]
            == [("polyIUse", "2818")], "NI6220 channel operation census changed")
    exact_wires(frame, (
        ("1808", "283"), ("1770", "233"), ("2593", "2832"),
        ("2442", "2525"), ("2408", "2457"), ("2549", "2584"),
        ("2469", "2566"), ("3413", "2402"), ("3693", "2399"),
        ("3390", "2411"), ("3706", "2492"), ("750", "2476"),
        ("842", "1351", "643"), ("640", "2682"), ("2575", "3464"),
        ("3539", "2737"), ("2677", "2700"), ("3649", "2638"),
        ("3659", "2635"), ("2644", "2694"), ("3670", "2620"),
        ("3680", "2602"), ("3719", "2423"), ("3732", "2417"),
        ("2690", "2429"), ("2686", "2396")), "NI6220 initializer root")
    exact_wires(body, (
        ("280", "2833"), ("99", "2839"), ("1345", "2859"),
        ("616", "2845"), ("2703", "2915"), ("2740", "2895"),
        ("2697", "2824"), ("2951", "2693"), ("2850", "2689")), "NI6220 channel body")
    for uid, klass, label, selector in (
        ("2629", "iUse", "DAQmx Create Task.vi", None),
        ("2818", "polyIUse", "DAQmx Create Virtual Channel.vi", "02"),
        ("2393", "polyIUse", "DAQmx Timing.vi", "02"),
        ("2454", "polyIUse", "DAQmx Trigger.vi", "03"),
    ):
        node = unique(bd, klass, uid)
        require(node.findtext("label/textRec/text") == f'"{label}"'
                and [int(t.findtext("dco/paramIdx") or "0") for t in node.findall("termList/*")]
                == list(range(16)), "NI6220 initializer call contract changed")
        if selector is not None:
            require(node.findtext("instanceSelector/menuInstanceUsed") == selector,
                    "NI6220 initializer polymorphic selection changed")
    require(tag_array(constant(frame, "842")) == [f"11/ai{i}" for i in range(16)],
            "NI6220 physical channel list changed")
    ranges = tuple(10.0 if i in (4, 5, 6, 7) else 0.2 for i in range(16))
    for uid, expected in (("1808", ranges), ("1770", tuple(-v for v in ranges))):
        payload = bytes.fromhex(constant(frame, uid))
        require(len(payload) == 132 and payload[:4] == bytes.fromhex("00000010")
                and struct.unpack(">16d", payload[4:]) == expected,
                "NI6220 voltage range array changed")
    for uid, expected in (
        ("3732", "0000000C4F6E626F617264436C6F636B"), ("3719", "00002828"),
        ("3706", "00002828"), ("3693", "000027C2"), ("3680", "000028B9"),
        ("3670", "01"), ("3659", "0000000943315F4E4936323230"), ("3649", "01"),
        ("3539", "0000286C"), ("750", "000000082F31312F50464930"),
    ):
        require(constant(frame, uid) == expected, "NI6220 initializer literal argument changed")
    require(constant(body, "616") == "00002763", "NI6220 input mode is not RSE")
    for outer, inner in (("1351", "1345"), ("233", "99"), ("283", "280")):
        tunnel = loop.find(f"termList/*[@uid='{outer}']/dco")
        require(tunnel is not None and tunnel.get("class") == "lpTun"
                and tunnel.findtext("TunnelType") == "01"
                and [t.get("uid") for t in tunnel.findall("termList/*")] == [inner, outer],
                "NI6220 initializer auto-index tunnel changed")
    size = unique(bd, "prim", "634")
    require(size.findtext("primResID") == "1809" and size.findtext("primIndex") == "139",
            "NI6220 channel-count Array Size primitive changed")
    prop = unique(bd, "propNode", "2561")
    require([p.findtext("PropItemCode") for p in prop.findall(".//*[@class='propItemInfo']")]
            == ["6410", "6182"]
            and all(p.findtext("objFlags") == "4096"
                    for p in prop.findall(".//*[@class='propItemInfo']")),
            "NI6220 Read properties/write mode changed")
    return "NI6220 INIT: sixteen RSE channels; +/-10 V at ai4..7, +/-0.2 V elsewhere; finite rising OnboardClock sampling with parent rate/count, separate rising /11/PFI0 trigger; Read AutoStart=True; no explicit Start Task"


def validate_read_tree(roots):
    bd, fp = roots["vi_BDHb.xml"], roots["vi_FPHb.xml"]
    frame = bd.find("root")
    require(connector_map(fp) == [(0, "977"), (3, "1705"), (8, "1072"), (9, "761"), (11, "163")],
            "NI6220 reader connector mapping changed")
    for uid, control in (("763", "761"), ("168", "163"), ("1074", "1072"),
                         ("979", "977"), ("1707", "1705")):
        require(unique(bd, "fPTerm", uid).find("dco").get("uid") == control,
                "NI6220 reader public terminal identity changed")
    reader = unique(bd, "polyIUse", "1269")
    require(reader.findtext("label/textRec/text") == '"DAQmx Read.vi"'
            and reader.findtext("instanceSelector/menuInstanceUsed") == "08",
            "NI6220 Read polymorphic instance changed")
    require([int(t.findtext("dco/paramIdx") or "0") for t in reader.findall("termList/*")]
            == list(range(16)), "NI6220 Read connector inventory changed")
    require(constant(frame, "57") == "BFF0000000000000", "NI6220 Read timeout is not -1")
    require(constant(frame, "1160") == "0000", "NI6220 scaling selector is not False")
    exact_wires(frame, (
        ("168", "1272"), ("763", "2442", "1293"), ("1187", "1310"),
        ("1290", "276", "1192"), ("1317", "979"), ("1160", "885"),
        ("1016", "1707"), ("1152", "1001"), ("57", "1299"), ("1074", "1305"),
    ), "NI6220 reader root")
    loop = unique(bd, "forLoop", "612")
    require(loop.find("termList/*[@uid='2442']/dco").get("class") == "lMax",
            "NI6220 mean For bound terminal changed")
    for uid in ("276", "1152"):
        require(loop.find(f"termList/*[@uid='{uid}']/dco/TunnelType").text == "01",
                "NI6220 mean array indexing changed")
    exact_wires(loop.find("diagramList")[0], (("272", "551"), ("554", "1147")), "NI6220 mean body")
    selector = unique(bd, "select", "861")
    require([(a.findtext("start"), a.findtext("diagramIdx")) for a in selector.findall("SelectRangeArray32/*")]
            == [("0", "0"), ("1", "1")], "NI6220 scaling Case polarity changed")
    false_arm, true_arm = selector.find("diagramList")
    require(false_arm.get("uid") == "869" and len(false_arm.find("zPlaneList")) == 0,
            "NI6220 False scaling operations changed")
    exact_wires(false_arm, (("999", "1014"),), "NI6220 False scaling arm")
    require(true_arm.get("uid") == "875", "NI6220 unreachable True arm moved")
    exact_wires(true_arm, (("677", "1015"), ("804", "683"), ("756", "667"),
                           ("659", "680"), ("1000", "663")), "NI6220 True scaling arm")
    return "NI6220 Read passes errors directly, requests timeout -1, and uses the supplied sample-count net as both DAQ sample count and mean-For N; False scaling is fixed"


def validate_runtime_boundary(root):
    initializer = unique(root, "iUse", "198078")
    public_term(initializer, "198099", 4)
    public_term(initializer, "198093", 2)
    public_term(initializer, "198102", 5)
    public_term(initializer, "198108", 7)
    parent = unique(root, "gRef", "91287")
    startup = next(d for d in root.iter() if d.get("class") == "diag"
                   and initializer in d.findall("zPlaneList/*"))
    require(parent.findtext("termList/*/dco/paramIdx") == "57"
            and unique(root, "gRef", "91986").findtext("termList/*/dco/paramIdx") == "58"
            and unique(root, "gRef", "81412").findtext("termList/*/dco/paramIdx") == "56",
            "NI6220 parent initializer sample/frequency/task banks changed")
    for source, target in (("91297", "198099"), ("91996", "198093"),
                           ("198102", "81422"), ("198108", "50038")):
        direct(startup, source, target)
    loop = unique(root, "whileLoop", "47483")
    frame = loop.find("diagramList")[0]
    require(frame.get("uid") == "47487", "NI6220 runtime body moved")
    call = unique(root, "iUse", "44966")
    require(call in frame.find("zPlaneList")
            and call.findtext("label/textRec/text") == '"1_ACQ_READ_NI6220.vi"',
            "NI6220 runtime reader call moved or changed")
    public_term(call, "45004", 9)
    public_term(call, "45010", 11)
    public_term(call, "45001", 8)
    public_term(call, "44973", 0)
    public_term(call, "44983", 3)
    exact_wires(frame, (("44983", "47134"), ("47493", "196782"),
                        ("48198", "45004"), ("44973", "48160"),
                        ("48186", "45010"), ("47528", "47924"),
                        ("47561", "47496")), "NI6220 runtime body")
    require(unique(root, "gRef", "48193").findtext("termList/*/dco/paramIdx") == "57",
            "NI6220 sample-count source bank changed")
    require(unique(root, "gRef", "48181").findtext("termList/*/dco/paramIdx") == "56",
            "NI6220 runtime task source bank changed")
    require(unique(root, "gRef", "47557").findtext("termList/*/dco/paramIdx") == "30"
            and unique(root, "lTst", "47497").findtext("objFlags") == "65537",
            "NI6220 runtime stop source or polarity changed")
    return "Runtime stop=True is a separate loop test, not a cancellation input to NI6220 Read; outer cleanup requires the read/iteration to complete"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_members_archive", type=Path)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    roots = checked_ni6220_roots(args.original_members_archive)
    print(validate_initializer_error(roots["1_ACQ_INIT_NI6220.vi"]))
    print(validate_initializer_configuration(roots["1_ACQ_INIT_NI6220.vi"]))
    print(validate_read_tree(roots["1_ACQ_READ_NI6220.vi"]))
    print(validate_runtime_boundary(checked_root(args.root_archive)))
    print("PASS: NI6220 error/read/stop boundary")


if __name__ == "__main__":
    main()
