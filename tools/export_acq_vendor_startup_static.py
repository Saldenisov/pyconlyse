"""Extract pinned copied TPG source resources; never load or execute LabVIEW."""

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_DIRECTORY = Path(r"C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\TPG300")
SOURCES = (
    (
        "Initialize.vi",
        "A64EC13F3EBECEF4C47B7208B0F8B8F49E5E0F54F3D65C6604284C0EE9736481",
    ),
    (
        "SubVI/TPG300-Serial Init.vi",
        "61712932DA9D07634CE5FDB49D69FE2BC048E597D3F8CC9C754CBA7C85F46082",
    ),
    (
        "SubVI/TPG300-Driver Core.vi",
        "7A0ECCF170459E5B56F49E38AA613246B17D09E9E118ABC73BE2C0B019488F2B",
    ),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_directory", type=Path)
    target = parser.parse_args().export_directory.resolve()
    if target.exists():
        raise FileExistsError(
            "exports must use a new directory; do not overwrite evidence"
        )
    for relative, expected in SOURCES:
        if digest(SOURCE_DIRECTORY / relative) != expected:
            raise AssertionError("copied source identity changed: " + relative)
    from lvkit.extractor import _extract_in_process

    target.mkdir(parents=True, exist_ok=False)
    records = []
    for relative, expected in SOURCES:
        source = SOURCE_DIRECTORY / relative
        destination = target / source.stem
        destination.mkdir()
        _extract_in_process(source, destination, "vi")
        if digest(source) != expected:
            raise AssertionError("source changed during extraction: " + relative)
        hashes = {
            name: digest(destination / name)
            for name in ("vi.xml", "vi_BDHb.xml", "vi_FPHb.xml")
        }
        records.append(
            {
                "source_relative_path": relative,
                "source_sha256": expected,
                "export_directory": str(destination),
                "xml_sha256": hashes,
            }
        )
    (target / "source_export_manifest.json").write_text(
        json.dumps(
            {"mode": "static-resource-extraction-only", "sources": records}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
