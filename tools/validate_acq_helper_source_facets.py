"""Cross-index37 previously proved helper graphs and exclude two dormant VIs.

This reuses independent initializer/read/deviation proofs. It does not turn
their documented driver/default/error-seed limitations into full coverage.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from build_acq_saved_diagram_census import call_names
from validate_acq_deviation_helpers import PROFILES
from validate_acq_deviation_helpers import checked_roots as deviation_roots
from validate_acq_deviation_helpers import validate_tree as validate_deviation
from validate_acq_modulator_start_event_guards import require
from validate_acq_ni6071e_initializer import checked_roots as ai_roots
from validate_acq_ni6071e_initializer import validate_trees as validate_ai
from validate_acq_ni6220_read_error_contract import (
    ALL_MEMBERS_ARCHIVE_SHA256,
    checked_ni6220_roots,
    validate_initializer_configuration,
    validate_initializer_error,
    validate_read_tree,
)
from validate_acq_ni6602_initializer import checked_roots as counter_roots
from validate_acq_ni6602_initializer import validate_trees as validate_counter
from validate_acq_output_initializers import checked_roots as output_roots
from validate_acq_output_initializers import validate_ao, validate_dio

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = (
    REPO
    / "legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip"
)
DORMANT = {
    "1_ACQ_INIT_NI6259.vi": ("3", "2798"),
    "1_ACQ_READ_NI6259.vi": ("3", "869", "875", "639"),
}


def validate_dormant(path=ARCHIVE):
    """No inbound saved IUVI links across all17 original members.

    Exclusion is from this static call graph, not every possible VI Server or
    external caller. Their six diagrams remain outside reachable root
    behavior. The separate validate_acq_ni6259_dormant validator now supplies
    bounded wire facets; this exclusion-only result does not certify them.
    """
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper()
        == ALL_MEMBERS_ARCHIVE_SHA256,
        "original17-member archive changed",
    )
    links = []
    with ZipFile(path) as archive:
        require(len(archive.namelist()) == 51, "original member population changed")
        members = sorted({n.split("/")[0] for n in archive.namelist()})
        require(len(members) == 17, "original VI population changed")
        for member in members:
            meta = ET.fromstring(archive.read(member + "/vi.xml"))
            links.extend((member, uid, name) for uid, name in call_names(meta).items())
        require(
            not any(name.rsplit(":", 1)[-1] in DORMANT for _, _, name in links),
            "NI6259 now has a static inbound call",
        )
        for member, expected in DORMANT.items():
            root = ET.fromstring(archive.read(member + "/vi_BDHb.xml"))
            require(
                tuple(d.get("uid") for d in root.findall(".//*[@class='diag']"))
                == expected,
                "dormant saved diagrams changed",
            )
    return {
        "members_checked": 17,
        "dormant_diagrams": 6,
        "static_inbound_calls": (),
        "business_logic_translated": False,
    }


def validate_helpers():
    # NI6071E export has a separate pinned receipt for the same original VI.
    validate_ai(ai_roots(ARCHIVE.parent / "1_ACQ_INIT_NI6071E_XML_shafeb8.zip"))
    outputs = output_roots(ARCHIVE)
    validate_dio(outputs["1_ACQ_INIT_DIO96.vi"])
    validate_ao(outputs["1_ACQ_INIT_NI6703.vi"])
    ni6220 = checked_ni6220_roots(ARCHIVE)
    validate_initializer_error(ni6220["1_ACQ_INIT_NI6220.vi"])
    validate_initializer_configuration(ni6220["1_ACQ_INIT_NI6220.vi"])
    validate_read_tree(ni6220["1_ACQ_READ_NI6220.vi"])
    validate_counter(counter_roots(ARCHIVE))
    deviations = deviation_roots(ARCHIVE)
    for name, profile in PROFILES.items():
        validate_deviation(deviations[name], profile)
    return {"cross_indexed_helper_diagrams": 37, "dormant": validate_dormant()}


if __name__ == "__main__":
    print(validate_helpers())
