"""Pin the 11 typed DBL Index Array outputs in the saved NI6220 caller.

NI's archived User Manual (320999e, table5-1 and section6, Indexing Arrays)
establishes out-of-bounds -> element-type default, DBL -> 0.0. This proof
does not infer failed driver returns, Mean state, Case defaults or cluster
conversion padding. Existing caller proof independently pins all wires.
"""

import json

from qualify_acq_beamline_fragments import ROOT_ARCHIVE
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_runtime import validate_runtime
from validate_acq_runtime_io_frame import heap_type
from validate_acq_vam_status import checked_vam

# UID: frame, array port/heap, output-index ports, first output heap,
#      saved node flags/shortCount, literal indices (None for supplied U16).
INDEX_NODES = {
    "52275": (
        "47080",
        "52281",
        2687,
        (
            ("52284", "52287"),
            ("53076", "53081"),
            ("53085", "53088"),
            ("53091", "53094"),
        ),
        2688,
        "524288",
        "2",
        (4, 5, 6, 7),
    ),
    "48881": (
        "48574",
        "48884",
        2749,
        (
            ("48887", "48892"),
            ("48897", "48902"),
            ("48905", "48908"),
            ("48911", "48914"),
            ("48917", "48920"),
            ("48923", "48926"),
        ),
        2750,
        "524288",
        "2",
        (0, 1, 2, 3, 8, 9),
    ),
    "48810": (
        "48574",
        "48812",
        2770,
        (("48815", "48818"),),
        2771,
        None,
        "20",
        None,
    ),
}


def _term(node, port, heap_id, kind, term_flags, dco_flags, dsw, metadata):
    term = node.find(f"termList/*[@uid='{port}']")
    require(
        term is not None
        and term.get("class") == "term"
        and term.findtext("objFlags") == term_flags
        and term.find("dco").get("class") == "aIDCO"
        and term.findtext("dco/typeDesc") == f"TypeID({heap_id})"
        and term.findtext("dco/objFlags") == dco_flags
        and term.findtext("dco/dsw") == dsw,
        "NI6220 Index Array terminal shape changed: " + port,
    )
    descriptor, flat = heap_type(metadata, heap_id)
    require(descriptor.get("Type") == kind, "NI6220 index terminal type changed")
    if kind == "Array":
        dimensions = descriptor.findall("Dimension")
        members = descriptor.findall("TypeDesc")
        require(
            len(dimensions) == 1
            and dimensions[0].attrib == {"Flags": "0x00FF", "FixedSize": "0xFFFFFF"}
            and len(members) == 1
            and members[0].attrib == {"TypeID": "58"}
            and flat[58].get("Type") == "NumFloat64",
            "NI6220 input is not the saved one-dimensional DBL array",
        )


def validate_indices(root, metadata):
    validate_runtime(root, metadata)
    for uid, row in INDEX_NODES.items():
        frame, array_port, array_heap, pairs, first_heap, flags, short_count, _ = row
        node = unique(unique(root, "diag", frame), "aIndx", uid)
        require(
            node.findtext("objFlags") == flags
            and node.findtext("shortCount") == short_count,
            "NI6220 Index Array expansion mode changed",
        )
        _term(node, array_port, array_heap, "Array", "36928", "131072", None, metadata)
        for position, (output, index) in enumerate(pairs):
            _term(
                node,
                output,
                first_heap + 2 * position,
                "NumFloat64",
                "4160",
                "1" if position == 0 else "262145",
                None,
                metadata,
            )
            _term(
                node,
                index,
                first_heap + 2 * position + 1,
                "NumInt32",
                "299072" if uid == "48810" else "36928",
                "6291456",
                "2048" if uid == "48810" else "4096",
                metadata,
            )
    return {
        "index_nodes": 3,
        "scalar_outputs": 11,
        "typed_terminals": 25,
        "input_rank": 1,
        "output_type": "NumFloat64",
        "out_of_bounds_default": 0.0,
        "driver_failure_return_proven": False,
        "array_to_cluster_padding_proven": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate_indices(*checked_vam(ROOT_ARCHIVE)), sort_keys=True))
