"""Validate root startup PSP discovery/open wiring offline, no PSP calls."""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import checked_root, require, unique


def validate_tree(root):
    startup = unique(root, "sequence", "201").find("diagramList")
    require(len(startup) == 6 and startup[4].get("uid") == "21518",
            "PSP discovery startup stage changed")
    frame = startup[4]
    require({(n.get("class"), n.get("uid")) for n in frame.findall("zPlaneList/*[@class]")}
            == {("label", "74404"), ("forLoop", "74267"), ("prim", "74193"),
                ("gRef", "74186"), ("label", "22613")},
            "PSP discovery operation census changed")
    exact_wires(frame, (
        ("74407", "74219"), ("74273", "74189"), ("74395", "74207"),
        ("74195", "74293"), ("74198", "74279"), ("74224", "74204")),
        "PSP discovery frame")
    uri = bytes.fromhex(constant(frame, "74407"))
    require(uri[:4] == bytes.fromhex("00000023")
            and uri[4:] == b"ni.var.psp://10.20.30.2/SUPERVISION",
            "PSP discovery namespace changed")
    require(constant(frame, "74224") == "000000"
            and constant(frame, "74395") == "0000000000",
            "PSP enumeration filter literals changed")
    enumeration = unique(root, "prim", "74193")
    require(enumeration.findtext("primResID") == "23802"
            and enumeration.findtext("primIndex") == "551",
            "PSP enumerate primitive changed")
    require([(t.get("uid"), int(t.findtext("dco/parmIndex") or "0"))
             for t in enumeration.findall("termList/*")]
            == [("74195", 0), ("74198", 2), ("74201", 3), ("74204", 6),
                ("74207", 7), ("74210", 8), ("74213", 9), ("74216", 10), ("74219", 11)],
            "PSP enumerate terminal map changed")
    loop = unique(root, "forLoop", "74267")
    body = loop.find("diagramList")[0]
    require(body.get("uid") == "74296" and len(loop.find("diagramList")) == 1,
            "PSP discovery loop scope changed")
    require([(n.get("class"), n.get("uid")) for n in body.findall("zPlaneList/*[@class]")]
            == [("propNode", "74345"), ("sharedVariableDynamicOpen", "74325"), ("prim", "74317")],
            "PSP discovery body operation census changed")
    exact_wires(body, (
        ("74350", "74327"), ("74282", "74347"), ("74336", "74288"),
        ("74356", "74333"), ("74292", "74353"), ("74359", "74342"),
        ("74330", "74276"), ("74305", "74322")), "PSP discovery body")
    prop = unique(root, "propNode", "74345")
    require(prop.findtext("nodeName") == '"Variable PSP"'
            and [p.findtext("PropItemCode") for p in prop.findall(".//*[@class='propItemInfo']")]
            == ["17"], "PSP data-type property changed")
    require([(t.get("uid"), t.findtext("dco/objFlags")) for t in prop.findall("termList/*")]
            == [("74347", "65536"), ("74350", "262145"), ("74353", "131072"),
                ("74356", "524289"), ("74359", "1")],
            "PSP property terminal direction/read mode changed")
    opener = unique(root, "sharedVariableDynamicOpen", "74325")
    require(opener.findtext("SharedVariableDynamicResID") == "5CE3"
            and [(t.get("uid"), t.findtext("dco/terminal_ID") or "00")
                 for t in opener.findall("termList/*")]
            == [("74327", "0B"), ("74330", "03"), ("74333", "08"),
                ("74336", "00"), ("74339", "06"), ("74342", "0A")],
            "PSP dynamic-open terminal contract changed")
    wait = unique(root, "prim", "74317")
    require(wait.findtext("primResID") == "1302" and wait.findtext("primIndex") == "160"
            and constant(body, "74305") == "00000001",
            "PSP discovery 1-ms wait changed")
    require(len(loop.findall("termList/*")) == 5
            and loop.find("termList/*[@uid='74269']/dco").get("class") == "lMax",
            "PSP discovery For N/topology changed")
    for outer, inner in (("74273", "74276"), ("74279", "74282")):
        tunnel = loop.find(f"termList/*[@uid='{outer}']/dco")
        require(tunnel is not None and tunnel.get("class") == "lpTun"
                and tunnel.findtext("TunnelType") == "01"
                and [t.get("uid") for t in tunnel.findall("termList/*")] == [inner, outer],
                "PSP discovery reference indexing changed")
    left = loop.find("termList/*[@uid='74293']/dco")
    right = loop.find("termList/*[@uid='74285']/dco")
    require(left is not None and right is not None
            and left.get("class") == "lSR" and left.get("uid") == "74290"
            and right.get("class") == "rSR" and right.get("uid") == "74286"
            and [t.get("uid") for t in left.findall("termList/*")] == ["74292", "74293"]
            and [t.get("uid") for t in right.findall("termList/*")] == ["74288", "74285"]
            and left.find("rsrDCO").get("uid") == "74286"
            and right.find("lsrDCOList/*").get("uid") == "74290",
            "PSP discovery error shift-register pairing changed")
    bank_refs = [n for n in root.findall(".//*[@class='gRef']")
                 if n.findtext("termList/*/dco/paramIdx") == "61"]
    require([n.get("uid") for n in bank_refs] == ["74186"]
            and bank_refs[0].findtext("termList/*/objFlags") == "36864",
            "PSP discovery reference-bank writer/reader census changed")
    return [
        "Startup stage 4 enumerates ni.var.psp://10.20.30.2/SUPERVISION; auto-indexed child references drive For count; no expected-name/count/type whitelist check",
        "Per child: get Data Type, dynamic open, auto-index returned reference to local bank 61; 1-ms wait shares the iteration without a wire ordering against the open",
        "Enumerator error seeds loop error shift register; property/open errors feed subsequent iterations; final exterior error is unwired, with no handler or abort guard",
        "Bank 61 has exactly one write and no diagram-local read; final cleanup uses its separate fixed 27-tag array, not this discovered array; PSP close/open handle semantics are not inferred",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_export_zip", type=Path)
    for line in validate_tree(checked_root(parser.parse_args().root_export_zip)):
        print(line)
    print("PASS: ACQ PSP discovery controller wires")


if __name__ == "__main__":
    main()
