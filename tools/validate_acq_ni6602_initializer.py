"""Check all eight NI6602 initializer frames at abstract DAQmx boundaries.

Offline source-wire proof; no NI/PSP/VISA import or VI execution.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_read_error_contract import ALL_MEMBERS_ARCHIVE_SHA256, connector_map
from validate_acq_output_initializers import call, literal_string


HASHES = (
    "F1B17689D6DFFEB323423CC940267333F18A68CFA8823108BDE40231413C2CB7",
    "A9653FB95FE12520AD4DDCF40D6FDBEAD483B87336CE6D82BFF9A3DC49B7D87F",
    "827B1C150D60E92DC10D6F754657ECF12FD4A17DD9AA9D96A90DB16C657FA159",
)
# Frame UID, Create Task, channel, trigger, retrigger property, channel
# property, Timing, optional Start Task, error-in, error-out, task-out.
FRAMES = (
    ("9978", "7021", "10044", "10247", "7408", "8977", "9021", "9106", "16802", "13615", "7808"),
    ("8666", "9650", "8675", "8736", "9701", "9723", "9751", "9811", "13619", "12089", "8813"),
    ("6900", "8238", "8099", "8161", "8366", "8388", "8416", "8476", "12096", "13745", "9259"),
    ("9448", "11266", "9587", "11181", "12062", "12149", "12177", None, "13746", "13762", "12756"),
    ("7229", "7740", "7277", "7519", "7903", "7982", "8010", None, "13763", "17552", "11191"),
    ("6943", "10673", "10381", "10485", "10724", "10749", "10778", "10846", "17553", "13202", "6960"),
    ("9487", "11449", "10211", "11389", "11613", "11687", "11743", "11803", "13203", "13323", "12701"),
    ("7856", "11318", "7904", "8260", "8896", "10259", "10365", "10543", "13325", "13565", "12847"),
)
# Names, auto cleanup, physical counter, timebase, retriggerable, trigger
# source, trigger edge, channel idle, initial delay, high ticks, low ticks,
# property idle, timing mode, sample count, timebase edge.
LITERALS = (
    ("7797", "6946", "10172", "10197", "10236", "10315", "10330", "10358", "10345", "73", "10813", "9008", "9083", "9096", "9159"),
    ("9926", "9916", "10061", "10038", "10028", "10015", "10002", "9975", "9990", "9948", "9961", "9900", "9887", "9875", "9862"),
    ("8594", "8584", "8937", "8902", "8800", "8787", "8769", "8651", "8665", "8624", "8637", "8569", "8556", "8544", "8531"),
    ("12370", "12360", "12504", "12488", "12477", "12462", "12447", "12421", "12435", "12392", "12406", "12345", "12330", "12318", "12303"),
    ("8951", "8894", "9382", "9367", "9355", "9340", "9326", "9301", "9314", "9274", "9287", "8871", "8858", "8845", "8832"),
    ("10963", "10953", "11086", "11073", "11063", "11050", "11037", "11011", "11024", "10985", "10998", "10938", "10925", "10913", "10900"),
    ("11922", "11912", "12045", "12032", "12022", "12009", "11996", "11971", "11984", "11944", "11958", "11897", "11883", "11871", "11858"),
    ("11467", "11457", "11628", "11615", "8876", "11592", "11579", "11554", "11567", "11489", "11502", "10335", "10510", "10529", "10605"),
)
HIGH_TICKS = (20, 3620000, 200, 60, 60, 2000, 56, 100000)
LOW_TICKS = (31, 200, 43558, 43658, 43500, 101600, 43500, 20)
TRIGGER_PFI = (34, 34, 30, 34, 30, 30, 30, 10)
SEQUENCE_LOCALS = (
    ("12924", "00", ("13615", "13619", "13623", "13627", "13631", "13635", "13639", "13643")),
    ("11638", "01", ("11658", "12089", "12096", "12098", "12099", "13727", "13728", "13729")),
    ("13733", "02", ("13743", "13744", "13745", "13746", "13747", "13748", "13749", "13750")),
    ("12925", "03", ("13759", "13760", "13761", "13762", "13763", "17461", "17462", "17463")),
    ("12933", "04", ("12939", "17549", "17550", "17551", "17552", "17553", "17554", "17555")),
    ("1162", "05", ("13197", "13198", "13199", "13200", "13201", "13202", "13203", "13204")),
    ("13304", "06", ("13314", "13317", "13318", "13319", "13321", "13322", "13323", "13325")),
)
TUNNELS = (
    ("8775", ("7808", "8767", "8093", "9490", "7250", "10245", "9610", "8771", "8775")),
    ("8822", ("8809", "8813", "8096", "9513", "7259", "10252", "9613", "8818", "8822")),
    ("9267", ("9251", "9255", "9259", "9519", "7268", "10370", "10156", "9263", "9267")),
    ("12777", ("12743", "12747", "12752", "12756", "12761", "12765", "12769", "12773", "12777")),
    ("11203", ("9299", "11101", "11187", "9584", "11191", "11195", "10208", "11199", "11203")),
    ("7130", ("6870", "6875", "6880", "6887", "6897", "6960", "6996", "7013", "7130")),
    ("12711", ("12674", "12678", "12682", "12687", "12692", "12696", "12701", "12705", "12711")),
    ("12852", ("12816", "12820", "12825", "12829", "12834", "12839", "12843", "12847", "12852")),
    ("16834", ("16802", "16806", "16810", "16814", "16818", "16822", "16826", "16830", "16834")),
    ("13569", ("13537", "13541", "13545", "13549", "13553", "13557", "13561", "13565", "13569")),
)


def checked_roots(path):
    require(hashlib.sha256(path.read_bytes()).hexdigest().upper() == ALL_MEMBERS_ARCHIVE_SHA256,
            "original member archive hash changed")
    result = {}
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 51, "original XML member count changed")
        for name, expected in zip(("vi.xml", "vi_BDHb.xml", "vi_FPHb.xml"), HASHES):
            payload = archive.read("1_ACQ_INIT_NI6602.vi/" + name)
            require(hashlib.sha256(payload).hexdigest().upper() == expected,
                    f"NI6602 initializer XML hash changed: {name}")
            result[name] = ET.fromstring(payload)
    return result


def property_ports(bd, frame, uid, codes):
    node = unique(bd, "propNode", uid)
    require(node in frame.findall("zPlaneList/*"), "NI6602 property node moved")
    terms = node.findall("termList/*")
    require(len(terms) == 4 + len(codes), "NI6602 property connector count changed")
    require([int(t.findtext("dco/objFlags") or "0") for t in terms[:4]]
            == [65536, 262145, 131072, 524289],
            "NI6602 property task/error direction changed")
    properties = [t.find("dco/propList/*") for t in terms[4:]]
    require([p.findtext("PropItemCode") for p in properties] == codes
            and all(p.findtext("objFlags") == "4096" for p in properties),
            "NI6602 property code/write mode changed")
    return [t.get("uid") for t in terms]


def validate_trees(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(connector_map(fp) == [(0, "13107"), (1, "13106"), (4, "13026")],
            "NI6602 public connector map changed")
    require([n.get("Flags") for n in meta.findall("CPMp/Section/TypeDesc")]
            == ["0x0200", "0x0000", "-1", "-1", "0x0100", "-1", "-1", "-1"],
            "NI6602 public-to-local mapping changed")
    for terminal, control in (("13028", "13026"), ("13111", "13107"), ("13108", "13106")):
        require(unique(bd, "fPTerm", terminal).find("dco").get("uid") == control,
                "NI6602 public terminal identity changed")
    require([n.get("uid") for n in bd.findall(".//*[@class='gRef']")] == ["243"]
            and unique(bd, "gRef", "243").findtext("termList/*/dco/paramIdx", "0") == "0",
            "NI6602 task-local or hidden error alias changed")
    sequence = unique(bd, "sequence", "3868")
    frames = sequence.findall("diagramList/*")
    require([f.get("uid") for f in frames] == [r[0] for r in FRAMES]
            and len(bd.findall(".//*[@class='diag']")) == 9,
            "NI6602 initializer sequence order/scope changed")
    require({(n.get("class"), n.get("uid")) for n in bd.find("root/zPlaneList")
             if n.get("class") not in {None, "label"}}
            == {("nMux", "965"), ("gRef", "243"), ("sequence", "3868")},
            "NI6602 root operation census changed")
    exact_wires(bd.find("root"), (
        ("12852", "13593"), ("12711", "13590"), ("7130", "13195"),
        ("11203", "13192"), ("12777", "13189"), ("9267", "13186"),
        ("8822", "13181"), ("8775", "1040"), ("1000", "13108"),
        ("383", "1032"), ("13569", "13111"), ("13028", "16834")), "NI6602 root")
    for i, row in enumerate(FRAMES):
        (frame_uid, create_uid, channel_uid, trigger_uid, retrigger_uid,
         channel_prop_uid, timing_uid, start_uid, error_in, error_out, task_out) = row
        frame = frames[i]
        def ports(uid, label, selector=None):
            return [t.get("uid") for t in call(bd, frame, uid, label, selector)]
        create = ports(create_uid, "DAQmx Create Task.vi")
        channel = ports(channel_uid, "DAQmx Create Virtual Channel.vi", "33")
        trigger = ports(trigger_uid, "DAQmx Trigger.vi", "03")
        timing = ports(timing_uid, "DAQmx Timing.vi", "06")
        start = ports(start_uid, "DAQmx Start Task.vi") if start_uid else None
        retrigger = property_ports(bd, frame, retrigger_uid, ["6415"])
        channel_prop = property_ports(bd, frame, channel_prop_uid, ["4464", "833"])
        expected_operations = {
            ("iUse", create_uid), ("polyIUse", channel_uid), ("polyIUse", trigger_uid),
            ("polyIUse", timing_uid), ("propNode", retrigger_uid), ("propNode", channel_prop_uid),
        }
        if start_uid:
            expected_operations.add(("iUse", start_uid))
        require({(n.get("class"), n.get("uid")) for n in frame.findall("zPlaneList/*")
                 if n.get("class") not in {None, "label"}} == expected_operations,
                f"NI6602 frame {i} operation census changed")
        literal_string(frame, LITERALS[i][0], f"OUT{i}")
        literal_string(frame, LITERALS[i][2], f"10/ctr{i}")
        literal_string(frame, LITERALS[i][3], "/10/PFI11")
        literal_string(frame, LITERALS[i][5], f"/10/PFI{TRIGGER_PFI[i]}")
        literals = LITERALS[i]
        for j, value in {1: "01", 4: "01", 6: "000027BB" if i == 7 else "00002828",
                         7: "000027E6", 8: "0000000000", 9: f"{HIGH_TICKS[i]:08X}",
                         10: f"{LOW_TICKS[i]:08X}", 11: "000027E6",
                         12: "000027C2", 13: "00000001", 14: "00002828"}.items():
            require(constant(frame, literals[j]) == value,
                    f"NI6602 frame {i} literal argument {j} changed")
        destinations = (create[1], create[2], channel[5], channel[9], retrigger[4],
                        trigger[5], trigger[7], channel[12], channel[13], channel[1],
                        channel[2], channel_prop[4], timing[1], timing[2], channel_prop[5])
        wires = list(zip(literals, destinations)) + [
            (error_in, create[11]), (create[4], channel[0]), (create[15], channel[11]),
            (channel[4], trigger[0]), (channel[15], trigger[11]),
            (trigger[4], retrigger[0]), (trigger[15], retrigger[2]),
            (retrigger[1], channel_prop[0]), (retrigger[3], channel_prop[2]),
            (channel_prop[1], timing[0]), (channel_prop[3], timing[11]),
        ]
        if start:
            wires += [(timing[4], start[0]), (timing[15], start[11]),
                      (start[4], task_out), (start[15], error_out)]
        else:
            wires += [(timing[4], task_out), (timing[15], error_out)]
        exact_wires(frame, wires, f"NI6602 frame {i}")
    require(len(sequence.findall("termList/*")) == 10, "NI6602 sequence tunnel count changed")
    for outer, ports in TUNNELS:
        tunnel = sequence.find(f"termList/*[@uid='{outer}']/dco")
        require(tunnel is not None and tunnel.get("class") == "seqTun"
                and [t.get("uid") for t in tunnel.findall("termList/*")] == list(ports)
                and tunnel.findtext("objFlags") == ("2048" if outer == "16834" else "2049"),
                "NI6602 sequence task/error tunnel changed")
    require(len(sequence.findall("seqLocDCOList/*")) == 7,
            "NI6602 sequence error-local count changed")
    for uid, defined, ports in SEQUENCE_LOCALS:
        local = unique(bd, "sLoc", uid)
        require(local.findtext("diagDefined", "00") == defined
                and [t.get("uid") for t in local.findall("termList/*")] == list(ports),
                "NI6602 cross-frame error local changed")
    bundle = unique(bd, "nMux", "965")
    field_terms = ("1040", "13181", "13186", "13189", "13192", "13195", "13590", "13593")
    require(len(bundle.findall("termList/*")) == 10, "NI6602 bundle field count changed")
    for index, uid in enumerate(field_terms):
        field = bundle.find(f"termList/*[@uid='{uid}']/dco")
        require(field is not None and int(field.findtext("i") or "0") == index,
                "NI6602 output task field changed")
    return [
        "Eight fixed OUT0..OUT7 tasks on 10/ctr0..7; timebase /10/PFI11; finite one-pulse timing; idle Low; retriggerable True; initial-delay literal zero",
        f"High ticks {HIGH_TICKS}; low ticks {LOW_TICKS}; trigger PFIs {TRIGGER_PFI}; trigger edge falling only at ctr7; timebase active edge rising throughout",
        "Start Task appears only at ctr0/1/2/5/6/7; continuous public error-in -> eight frame-local chains -> public error-out; no error clear/recovery branch",
        "All eight task outputs preserve corresponding cluster fields; request dataflow does not prove task success or external timebase frequency",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_member_archive", type=Path)
    for line in validate_trees(checked_roots(parser.parse_args().original_member_archive)):
        print(line)
    print("PASS: complete eight-frame NI6602 initializer controller wires")


if __name__ == "__main__":
    main()
