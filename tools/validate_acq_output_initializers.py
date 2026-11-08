"""Prove DIO96 and NI6703 saved initializer dataflow without device access.

Standard DAQmx calls are abstract boundaries, not executed or emulated.
Only connected literals and wires are assigned controller semantics.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from validate_acq_final_cleanup import constant, exact_wires, tag_array, public_term
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_read_error_contract import ALL_MEMBERS_ARCHIVE_SHA256, connector_map


HASHES = {
    "1_ACQ_INIT_DIO96.vi": (
        "69B963C4950FF450F8ECA52B77AF8347D57F1390E3153B95BE5270243038F851",
        "8A2A5B11BA327B6DD2D5E2927072BD85CAA0EC1C76FD2A055A39C07303C5C189",
        "039F302CD5B4B416E3469E179FBC8F7631A2C7EF8AD4404E17FEB3482687EBF1",
    ),
    "1_ACQ_INIT_NI6703.vi": (
        "7BC26B89AC0CEEE6D5334E9635242463368DC906316C9B61060D9D6A952C6BDE",
        "15BD09DA2ACDEA6ADA5E51B094D062F100914817F1882864E6584761A70FAB2A",
        "9A2B7838079E48F72C5154FE06E22069DDBF643F59F1CC5D9A1295FC93DF2F43",
    ),
}
NAMES = ("vi.xml", "vi_BDHb.xml", "vi_FPHb.xml")


def checked_roots(path):
    require(hashlib.sha256(path.read_bytes()).hexdigest().upper() == ALL_MEMBERS_ARCHIVE_SHA256,
            "original member archive hash changed")
    result = {}
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 51, "original XML member count changed")
        for member, hashes in HASHES.items():
            result[member] = {}
            for name, expected in zip(NAMES, hashes):
                payload = archive.read(member + "/" + name)
                require(hashlib.sha256(payload).hexdigest().upper() == expected,
                        f"output initializer XML hash changed: {member}/{name}")
                result[member][name] = ET.fromstring(payload)
    return result


def public_contract(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    require(connector_map(fp) == [(0, "1280"), (1, "60"), (4, "580")],
            "output initializer connector map changed")
    require([n.get("Flags") for n in meta.findall("CPMp/Section/TypeDesc")]
            == ["0x0100", "0x0200", "-1", "-1", "0x0000", "-1", "-1", "-1"],
            "output initializer local mapping changed")
    for terminal, control in (("583", "580"), ("1282", "1280"), ("62", "60")):
        require(unique(bd, "fPTerm", terminal).find("dco").get("uid") == control,
                "output initializer public terminal identity changed")
    # All locals are task-cluster aliases (index 2); no hidden public error alias.
    require(all(n.findtext("termList/*/dco/paramIdx") == "2"
                for n in bd.findall(".//*[@class='gRef']")),
            "output initializer gained non-task local alias")
    return bd


def call(bd, frame, uid, label, selector=None):
    klass = "iUse" if selector is None else "polyIUse"
    node = unique(bd, klass, uid)
    require(node in frame.findall("zPlaneList/*")
            and node.findtext("label/textRec/text") == f'"{label}"',
            f"output initializer call {uid} moved or changed")
    terms = node.findall("termList/*")
    require(len(terms) == 16, "output initializer call connector size changed")
    for slot, term in enumerate(terms):
        public_term(node, term.get("uid"), slot)
    if selector is not None:
        require(node.findtext("instanceSelector/menuInstanceUsed") == selector,
                "output initializer polymorphic selection changed")
    return terms


def literal_string(frame, uid, expected):
    payload = bytes.fromhex(constant(frame, uid))
    require(len(payload) >= 4 and int.from_bytes(payload[:4], "big") == len(payload) - 4
            and payload[4:].decode("ascii") == expected,
            f"output initializer string {uid} changed")


def validate_dio(roots):
    bd = public_contract(roots)
    frame = bd.find("root")
    require(frame.get("uid") == "3"
            and len(bd.findall(".//*[@class='diag']")) == 1,
            "DIO initializer gained a nested diagram")
    require(Counter(n.get("class") for n in frame.findall("zPlaneList/*[@class]"))
            == {"label": 6, "iUse": 6, "polyIUse": 6, "nMux": 1, "gRef": 1},
            "DIO initializer operation census changed")
    expected_wires = (
        ("2107", "1282"), ("1441", "1837"), ("583", "2509"),
        ("1755", "342"), ("2073", "411"), ("1908", "408"), ("1360", "953"),
        ("1816", "1743"), ("1849", "1776"), ("1854", "1807"),
        ("1865", "1810"), ("1875", "1758"), ("2036", "1911"),
        ("2026", "1962"), ("2015", "1959"), ("2010", "1929"),
        ("1968", "1889"), ("1788", "1990"), ("2134", "2050"),
        ("2167", "2095"), ("2172", "2125"), ("2183", "2128"),
        ("2193", "2077"), ("1941", "2155"), ("973", "868"),
        ("1119", "1492"), ("1533", "979"), ("1523", "1465"),
        ("1509", "1462"), ("1504", "1429"), ("1471", "920"),
        ("812", "863"), ("1393", "1170"), ("1149", "589"),
        ("1185", "846"), ("1190", "1140"), ("1204", "1143"),
        ("1214", "817"), ("2008", "1363"), ("1617", "951"),
        ("946", "62"), ("2537", "2480"), ("2526", "2477"),
        ("2521", "1381"), ("2486", "1348"),
    )
    exact_wires(frame, expected_wires, "DIO initializer")
    expected_calls = set()
    for i, (create, channel, task_uid, cleanup_uid, physical_uid, device, ports) in enumerate((
        ("2471", "1345", "2526", "2537", "2008", 3, "0:6"),
        ("1134", "579", "1190", "1204", "1214", 4, "0:7"),
        ("1456", "912", "1509", "1523", "1533", 5, "0:6"),
        ("1801", "1740", "1854", "1865", "1875", 3, "7:11"),
        ("1953", "1886", "2015", "2026", "2036", 4, "8:11"),
        ("2119", "2047", "2172", "2183", "2193", 5, "7:11"),
    )):
        call(bd, frame, create, "DAQmx Create Task.vi")
        call(bd, frame, channel, "DAQmx Create Virtual Channel.vi", "23" if i < 3 else "24")
        expected_calls.update((create, channel))
        literal_string(frame, task_uid, f"C{device}_{'IN' if i < 3 else 'OUT'}_DIO")
        literal_string(frame, physical_uid, f"{device}/port{ports}")
        require(constant(frame, cleanup_uid) == "01", "DIO auto cleanup is not True")
    require({n.get("uid") for n in bd.iter() if n.get("class") in {"iUse", "polyIUse"}}
            == expected_calls, "DIO initializer call set changed")
    bundle = unique(bd, "nMux", "939")
    fields = [n for n in bundle.findall("termList/*/dco") if n.get("class") == "nmxDCO"]
    require([(d.get("uid"), d.findtext("i") or "0") for d in fields]
            == [("947", "0"), ("960", "0"), ("862", "1"), ("867", "2"),
                ("341", "3"), ("407", "4"), ("410", "5")],
            "DIO task output field order changed")
    require({n.get("uid") for n in bd.findall(".//*[@class='gRef']")} == {"1579"},
            "DIO task-local census changed")
    return "DIO96: six ordered Create Task/channel pairs; continuous public error chain; task fields DI C3/C4/C5 then DO C3/C4/C5; no write/start/clear call"


AO_FRAMES = (
    # frame, loop, body, create, channel, task-name, cleanup, N, physical array
    ("1241", "714", "773", "2471", "847", "2526", "2537", "1211", "681"),
    ("2744", "4638", "4666", "4587", "4725", "5017", "5007", "4898", "3060"),
    ("1824", "1920", "1976", "1841", "2070", "2617", "2606", "2595", "1419"),
    ("355", "789", "862", "400", "1429", "3055", "3043", "3031", "3637"),
)
AO_FRAME_WIRES = (
    (("721", "953"), ("725", "1932"), ("1617", "951"), ("946", "2931"),
     ("2486", "729"), ("681", "735"), ("1211", "716"),
     ("2537", "2480"), ("2526", "2477"), ("583", "2509")),
    (("4644", "4824"), ("3060", "4658"), ("3509", "4623"), ("4648", "3519"),
     ("4813", "4823"), ("4820", "4831"), ("4602", "4652"),
     ("4898", "4640"), ("5007", "4596"), ("5017", "4593")),
    (("1419", "1967"), ("1940", "1837"), ("1834", "1902"), ("1931", "2189"),
     ("2170", "2187"), ("2178", "2214"), ("1869", "1960"),
     ("2595", "1922"), ("2606", "1861"), ("2617", "1851")),
    (("3637", "835"), ("801", "1282"), ("391", "767"), ("797", "2846"),
     ("2806", "2841"), ("2829", "2853"), ("588", "812"),
     ("3031", "791"), ("3043", "524"), ("3055", "433")),
)
AO_BODY_WIRES = (
    (("1765", "860"), ("2733", "854"), ("2571", "857"), ("738", "866"),
     ("808", "879"), ("732", "850"), ("898", "728"), ("863", "724")),
    (("4688", "4737"), ("4713", "4731"), ("4701", "4734"), ("4661", "4743"),
     ("4675", "4755"), ("4655", "4728"), ("4773", "4651"), ("4740", "4647")),
    (("2021", "2083"), ("2047", "2077"), ("2035", "2080"), ("1971", "2089"),
     ("1986", "2101"), ("1964", "2073"), ("2120", "1959"), ("2086", "1938")),
    (("1208", "1817"), ("1408", "1478"), ("1359", "1621"), ("843", "1939"),
     ("1051", "2428"), ("824", "1433"), ("2572", "810"), ("1876", "800")),
)


def validate_ao(roots):
    bd = public_contract(roots)
    sequence = unique(bd, "sequence", "784")
    frames = sequence.findall("diagramList/*")
    require([f.get("uid") for f in frames] == [r[0] for r in AO_FRAMES]
            and not sequence.findall("termList/*")
            and len(bd.findall(".//*[@class='diag']")) == 9,
            "AO initializer sequence order/scope changed")
    require(Counter(n.get("class") for d in bd.iter() if d.get("class") == "diag"
                    for n in d.findall("zPlaneList/*[@class]"))
            == {"gRef": 8, "nMux": 4, "forLoop": 4, "iUse": 4,
                "polyIUse": 4, "sequence": 1},
            "AO initializer operation census changed")
    exact_wires(bd.find("root"), (), "AO initializer root")
    expected_calls = set()
    for i, (frame_uid, loop_uid, body_uid, create_uid, channel_uid,
            name_uid, cleanup_uid, n_uid, channels_uid) in enumerate(AO_FRAMES):
        frame = frames[i]
        loop = unique(bd, "forLoop", loop_uid)
        require(loop in frame.findall("zPlaneList/*"), "AO channel loop moved")
        body = loop.find("diagramList")[0]
        require(body.get("uid") == body_uid, "AO channel body changed")
        exact_wires(frame, AO_FRAME_WIRES[i], f"AO frame {i}")
        exact_wires(body, AO_BODY_WIRES[i], f"AO channel body {i}")
        create_terms = call(bd, frame, create_uid, "DAQmx Create Task.vi")
        channel_terms = call(bd, body, channel_uid, "DAQmx Create Virtual Channel.vi", "20")
        expected_calls.update((create_uid, channel_uid))
        literal_string(frame, name_uid, f"C{i + 6}_NI6703")
        require(constant(frame, cleanup_uid) == "01", "AO auto cleanup is not True")
        require(constant(frame, n_uid) == "0000000A", "AO channel bound is not ten")
        require(tag_array(constant(frame, channels_uid)) == [f"{i + 6}/ao{j}" for j in range(10)],
                "AO physical channel array changed")
        for uid, expected in zip(
            (("2733", "2571", "1765", "808"), ("4713", "4701", "4688", "4675"),
             ("2047", "2035", "2021", "1986"), ("1408", "1359", "1208", "1051"))[i],
            ("4024000000000000", "C024000000000000", "FFFFFFFF", "0000286C"),
        ):
            require(constant(body, uid) == expected, "AO range/default/units literal changed")
        terminal_config_uid = ("1765", "4688", "2021", "1208")[i]
        require(body.findtext(
            f"nodeList/*/termList/*[@uid='{terminal_config_uid}']/dco/ddo/partsList/"
            "*[@class='label']/textRec/text") == '"output terminal configuration"',
            "AO default terminal-configuration label changed")
        # No error shift register and no channel-error input. Earlier iterations
        # are not accumulated into the non-indexed error output.
        require(len(loop.findall("termList/*")) == 5
                and all(t.find("dco").get("class") in {"lMax", "lpTun"}
                        for t in loop.findall("termList/*")),
                "AO loop error accumulation topology changed")
        task_outer, task_inner, physical_outer, physical_inner, err_outer, err_inner = (
            (("729", "732", "735", "738", "725", "728"),
             ("4652", "4655", "4658", "4661", "4648", "4651"),
             ("1960", "1964", "1967", "1971", "1940", "1959"),
             ("812", "824", "835", "843", "801", "810"))[i])
        for outer, inner, kind in ((task_outer, task_inner, "00"),
                                   (physical_outer, physical_inner, "01"),
                                   (err_outer, err_inner, "00")):
            tunnel = loop.find(f"termList/*[@uid='{outer}']/dco")
            require(tunnel is not None and tunnel.get("class") == "lpTun"
                    and tunnel.findtext("TunnelType", "00") == kind
                    and [t.get("uid") for t in tunnel.findall("termList/*")] == [inner, outer],
                    "AO channel indexing/error exit changed")
        connected = {t.get("uid") for s in bd.findall(".//*[@class='signal']")
                     for t in s.findall("termList/*")}
        require(create_terms[15].get("uid") not in connected
                and channel_terms[11].get("uid") not in connected,
                "AO formerly unwired error port became connected")
    require({n.get("uid") for n in bd.iter() if n.get("class") in {"iUse", "polyIUse"}}
            == expected_calls, "AO initializer gained another call")
    for uid, definition, ports in (
        ("1916", "00", ["1932", "3509", "1831", "364"]),
        ("1970", "01", ["1977", "3519", "1834", "369"]),
        ("2000", "02", ["2008", "3524", "1837", "391"]),
    ):
        local = unique(bd, "sLoc", uid)
        require(local.findtext("diagDefined", "00") == definition
                and [t.get("uid") for t in local.findall("termList/*")] == ports,
                "AO cross-frame error sequence local changed")
    for field, uid, dco_uid in ((0, "939", "960"), (1, "4818", "4825"),
                               (2, "2175", "2190"), (3, "2820", "2847")):
        bundle = unique(bd, "nMux", uid)
        dco = bundle.find(f"termList/*/dco[@uid='{dco_uid}']")
        require(dco is not None and int(dco.findtext("i") or "0") == field,
                "AO task cluster field changed")
    require({n.get("uid") for n in bd.findall(".//*[@class='gRef']")}
            == {"2924", "1579", "4828", "4810", "2198", "2166", "2850", "2791"},
            "AO task-local census changed")
    return "NI6703: four ordered ten-channel +/-10 V task configurations; Create Task errors discarded, channel errors unseeded/unaccumulated; public error-out is C9 last-channel error only; no output voltage write"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_member_archive", type=Path)
    roots = checked_roots(parser.parse_args().original_member_archive)
    print(validate_dio(roots["1_ACQ_INIT_DIO96.vi"]))
    print(validate_ao(roots["1_ACQ_INIT_NI6703.vi"]))
    print("PASS: DIO96 and NI6703 initializer controller wire contracts")


if __name__ == "__main__":
    main()
