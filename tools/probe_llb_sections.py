"""Read-only diagnostics for classic LabVIEW LLB member payloads.

This does not execute VIs or modify the LLB. It reports per-section decode
success so partial library extraction cannot be mistaken for full coverage.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lvkit.extractor import _open_llb_vi


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("llb", type=Path)
    args = parser.parse_args()
    vi = _open_llb_vi(args.llb)
    for ident in ("UCRF", "CPRF", "ZCRF"):
        block = vi.get(ident)
        if block is None:
            continue
        print(f"{ident}: {len(block.sections)} sections")
        for number, section in sorted(block.sections.items()):
            name = (section.name_text or b"").decode(vi.textEncoding, errors="replace")
            try:
                data = block.getData(section_num=number).read()
                print(f"  {number:3d} OK   {len(data):7d} {name}")
            except Exception as exc:
                print(f"  {number:3d} FAIL {type(exc).__name__}: {exc} {name}")


if __name__ == "__main__":
    main()
