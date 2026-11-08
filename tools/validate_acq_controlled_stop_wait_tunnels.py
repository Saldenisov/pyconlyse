"""Trace phase-4/5 controlled-stop waits through saved sequence tunnels.

Usage: python tools/validate_acq_controlled_stop_wait_tunnels.py SOURCE_EXPORT_ZIP
Offline only: parses the hash-pinned XML, never imports a hardware adapter.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from validate_acq_cooling_start_completion import checked_root, require, unique


# Phase, phase diagram, nested sequence, source sRN/constant terminal,
# external sequence terminal, tunnel DCO, ordered internal frame terminals.
TUNNELS = (
    (4, "1722", "42397", "7985", "47276", "42403", "42404",
     ("42406", "42407", "42408", "42409", "42410", "42411",
      "42412", "42413", "42414", "42415", "42416", "42417",
      "42418", "42419", "42421")),
    (5, "52159", "54275", "52163", "52924", "54281", "54282",
     ("54284", "54285", "54286", "54287", "54288", "54289",
      "58834", "54290")),
)
WAIT_INPUTS = (
    (4, 0, "42513", "42520"),
    (4, 3, "42853", "42861"),
    (4, 6, "43240", "43246"),
    (4, 9, "43395", "43400"),
    (4, 12, "43566", "43571"),
    (5, 0, "54353", "54368"),
    (5, 3, "54508", "54513"),
    (5, 4, "54568", "54573"),
)


def direct(frame: ET.Element, source: str, target: str) -> None:
    matches = [signal for signal in frame.findall("signalList/*")
               if {source, target} <= {
                   term.get("uid") for term in signal.findall("termList/*")
               }]
    require(len(matches) == 1,
            f"expected one frame-local wire {source}->{target}")


def validate_tree(root: ET.Element) -> list[str]:
    """Check an already parsed tree; separate entry point permits mutation tests."""
    phases = unique(root, "sequence", "51954").find("diagramList")
    require(phases is not None and len(phases) == 7,
            "controlled-stop phase count changed")
    frames_by_phase = {}
    ports_by_phase = {}
    for (phase_index, phase_uid, sequence_uid, source_uid, literal_uid,
         external_uid, dco_uid, internal_uids) in TUNNELS:
        phase = phases[phase_index]
        require(phase.get("uid") == phase_uid, "phase diagram moved")
        sequence = unique(root, "sequence", sequence_uid)
        require(sequence in phase.findall("zPlaneList/*"),
                "nested sequence moved outside phase")
        source = unique(root, "sRN", source_uid)
        require(source in phase.findall("nodeList/*"),
                "constant source moved outside parent phase nodeList")
        terms = source.findall("termList/*")
        require(len(terms) == 1 and terms[0].get("uid") == literal_uid,
                "constant terminal changed")
        require(terms[0].findtext("dco/ConstValue") == "00000096"
                and terms[0].find("dco").get("class") == "bDConstDCO",
                "parent phase wait constant is not literal 150")
        direct(phase, literal_uid, external_uid)
        externals = sequence.findall("termList/*")
        require(len(externals) == 1 and externals[0].get("uid") == external_uid,
                "sequence external tunnel terminal changed")
        dco = externals[0].find("dco")
        require(dco is not None and dco.get("uid") == dco_uid
                and dco.get("class") == "seqTun",
                "external terminal no longer defines the sequence tunnel")
        require(tuple(term.get("uid") for term in dco.findall("termList/*"))
                == internal_uids + (external_uid,),
                "sequence tunnel frame-port list changed")
        frames = sequence.find("diagramList")
        require(frames is not None and len(frames) == len(internal_uids),
                "nested sequence frame count changed")
        for frame, port_uid in zip(frames, internal_uids):
            definitions = frame.findall(
                f"nodeList/*/termList/*[@class='term'][@uid='{port_uid}']")
            require(len(definitions) == 1,
                    f"internal port {port_uid} not defined in its frame")
            reference = definitions[0].find("dco")
            require(reference is not None and reference.get("uid") == dco_uid
                    and reference.get("class") is None,
                    f"port {port_uid} no longer references parent tunnel")
        frames_by_phase[phase_index] = frames
        ports_by_phase[phase_index] = internal_uids

    expected_wait_frames = {4: {0, 3, 6, 9, 12}, 5: {0, 3, 4}}
    for phase_index, frames in frames_by_phase.items():
        actual = set()
        for frame_index, frame in enumerate(frames):
            port = ports_by_phase[phase_index][frame_index]
            if any(port in {term.get("uid") for term in signal.findall("termList/*")}
                   for signal in frame.findall("signalList/*")):
                actual.add(frame_index)
        require(actual == expected_wait_frames[phase_index],
                f"phase {phase_index} connected tunnel frames changed: {actual}")

    for phase_index, frame_index, wait_uid, input_uid in WAIT_INPUTS:
        frame = frames_by_phase[phase_index][frame_index]
        wait = unique(root, "prim", wait_uid)
        require(wait in frame.findall("zPlaneList/*")
                and wait.findtext("primResID") == "1302",
                f"phase {phase_index} frame {frame_index} Wait moved")
        inputs = [term for term in wait.findall("termList/*")
                  if term.findtext("dco/parmIndex") == "1"]
        require(len(inputs) == 1 and inputs[0].get("uid") == input_uid,
                f"Wait {wait_uid} duration input changed")
        direct(frame, ports_by_phase[phase_index][frame_index], input_uid)
    return [
        "Phase 4 frames 0,3,6,9,12 each request Wait 150 ms through one "
        "parent literal and sequence tunnel",
        "Phase 5 frames 0,3,4 each request Wait 150 ms; frame 4 is the "
        "C3[4]=True restore frame, not another False frame",
        "Same-frame local-bank writes and Wait have no wait-after-write "
        "dependency established by this duration trace; physical pulse "
        "width and card-writer scheduling are not validated",
    ]


def validate(path: Path) -> list[str]:
    return validate_tree(checked_root(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    for line in validate(parser.parse_args().source_export_zip):
        print(line)
    print("PASS: ACQ controlled-stop eight 150-ms wait tunnel paths")


if __name__ == "__main__":
    main()
