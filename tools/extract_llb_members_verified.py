"""Extract every classic LLB member while keeping its source stream open.

lvkit 0.8.x's convenience extractor returns a lazy pylabview VI after its
underlying file handle closes. The first section of each block may be cached,
but later sections fail with ``ValueError: seek of closed file``. This audit
tool holds the file open, verifies RSRC member signatures, refuses conflicting
output files, and writes an extraction manifest. It never executes a VI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from lvkit.extractor import _make_read_po
from lvkit.text_encoding import labview_text_encoding
import pylabview.LVrsrcontainer as lvrsrc


UNSAFE = re.compile(r"[\\/*?:<>|\x00-\x1f]+")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def extract(llb_path: Path, output_dir: Path) -> dict:
    llb_path = llb_path.resolve(strict=True)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    po = _make_read_po(
        rsrc=str(llb_path), xml="", filebase=llb_path.stem,
        keep_names=True, raw_connectors=False,
    )
    members = []
    seen_names: set[str] = set()
    with llb_path.open("rb") as stream:
        vi = lvrsrc.VI(po, rsrc_fh=stream, text_encoding=labview_text_encoding())
        for block_name in ("UCRF", "CPRF", "ZCRF"):
            block = vi.get(block_name)
            if block is None:
                continue
            for section_number, section in sorted(block.sections.items()):
                if not section.name_text:
                    raise ValueError(f"Unnamed {block_name} section {section_number}")
                name = UNSAFE.sub("-", section.name_text.decode(vi.textEncoding, errors="replace")).strip()
                if name in seen_names:
                    raise ValueError(f"Duplicate member name: {name}")
                seen_names.add(name)
                payload = block.getData(section_num=section_number).read()
                if not payload.startswith(b"RSRC"):
                    raise ValueError(f"Not an RSRC member: {block_name} {section_number} {name}")
                destination = output_dir / name
                if destination.exists() and destination.read_bytes() != payload:
                    raise FileExistsError(f"Conflicting existing output: {destination}")
                if not destination.exists():
                    destination.write_bytes(payload)
                members.append({
                    "block": block_name,
                    "section": section_number,
                    "name": name,
                    "bytes": len(payload),
                    "sha256": sha256(payload),
                })
    manifest = {
        "source": str(llb_path),
        "source_bytes": llb_path.stat().st_size,
        "source_sha256": sha256(llb_path.read_bytes()),
        "member_count": len(members),
        "members": members,
    }
    manifest_path = output_dir / "extraction_manifest.json"
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != manifest_text:
        raise FileExistsError(f"Conflicting existing manifest: {manifest_path}")
    if not manifest_path.exists():
        manifest_path.write_text(manifest_text, encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("llb", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = extract(args.llb, args.output)
    print(f"members={manifest['member_count']}")
    print(f"source_sha256={manifest['source_sha256']}")
    print(args.output)


if __name__ == "__main__":
    main()
