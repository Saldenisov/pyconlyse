"""Print the offline display registry to stdout; never contact a Device Server."""

import argparse
import json

from supervision_reconstruction.domain.magnet_registry import candidate_registry
from supervision_reconstruction.domain.magnet_readback import magnet_display_snapshot


def render_snapshot(*, javascript: bool = False) -> str:
    registry = candidate_registry()
    snapshot = magnet_display_snapshot(registry)
    document = json.dumps(snapshot, ensure_ascii=True, indent=2)
    if javascript:
        return "// Generated display snapshot; not deployment authority.\nwindow.SUPERVISION_MAGNET_REGISTRY = " + document + ";\n"
    return document + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--javascript", action="store_true")
    args = parser.parse_args()
    print(render_snapshot(javascript=args.javascript), end="")
