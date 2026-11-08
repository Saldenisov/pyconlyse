"""Static copied pressure helper export; never open/run/save LabVIEW."""

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from export_acq_tpg_warning_static import digest

SOURCE = (
    Path(r"C:\dev\ELYSE-ACQ-analysis\source\10.20.30.10\TPG300\Data")
    / "TPG300-Get Pressure-Status.vi"
)
SOURCE_SHA256 = "00EAA9357276529C2B70FF44B2AC0C64CCA88D77FD3FF2C15844AA1CC51520B8"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    if args.directory.exists() or args.archive.exists():
        raise FileExistsError("new export directory and archive required")
    if digest(SOURCE) != SOURCE_SHA256:
        raise AssertionError("copied pressure source identity changed")
    from lvkit.extractor import _extract_in_process

    args.directory.mkdir(parents=True, exist_ok=False)
    _extract_in_process(SOURCE, args.directory, "vi")
    if digest(SOURCE) != SOURCE_SHA256:
        raise AssertionError("copied pressure source changed during export")
    files = ("vi.xml", "vi_BDHb.xml", "vi_FPHb.xml")
    record = {
        "source": str(SOURCE),
        "source_sha256": SOURCE_SHA256,
        "mode": "static-resource-extraction-only",
        "xml_sha256": {name: digest(args.directory / name) for name in files},
    }
    (args.directory / "source_export_manifest.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    with ZipFile(args.archive, "x") as archive:
        for name in (*files, "source_export_manifest.json"):
            archive.write(args.directory / name, name)
    print(json.dumps({**record, "archive_sha256": digest(args.archive)}, indent=2))


if __name__ == "__main__":
    main()
