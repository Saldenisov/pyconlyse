"""Exercise Web V0 load/treat/export routes against archived TRANCON pairs.

Software only: Tango construction fails immediately. Inputs remain unchanged.
The NumPy comparator follows the VI wires independently of generated lvkit code.
"""

import argparse
import csv
import hashlib
import os
import sys
from io import StringIO
from pathlib import Path

import numpy as np
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pump_probe_v0_api as api
from audit_trancon_saved_pairs import compare, read_raw, reconstructed_od
from zipfile import ZipFile


def unavailable_device(*_args, **_kwargs):
    raise AssertionError("Offline audit attempted a Tango call")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_paths", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = [path.resolve(strict=True) for path in args.zip_paths]
    os.environ["PYCONLYSE_PUMP_PROBE_DATA_ROOT"] = os.path.commonpath([str(path.parent) for path in paths])
    api._tango_proxy = unavailable_device
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_v0_api)
    records = []
    with app.test_client() as client:
        for path in paths:
            original = path.read_bytes()
            fingerprint = hashlib.sha256(original).hexdigest()
            with ZipFile(path) as archive:
                name = next(n for n in archive.namelist() if n.lower().endswith(".raw"))
                _wavelengths, _delays, raw = read_raw(archive.read(name))
            saved = np.loadtxt(path.with_suffix(".dat"))[1:, 1:].T
            loaded = client.post("/api/pump-probe-v0/data/load", json={"path": str(path)})
            if loaded.status_code != 200:
                raise AssertionError(loaded.get_json())
            preview = loaded.get_json()
            assert preview["raw_groups"] == ["BGI", "BGII", "IeI", "IeII", "I0I", "I0II"]
            for policy in ("retain", "drop_whole_zero"):
                request = {"path": str(path), "source_sha256": fingerprint,
                           "operations": [{"kind": "raw_od", "zero_slot_policy": policy}]}
                corrected = client.post("/api/pump-probe-v0/data/treat", json=request)
                exported = client.post("/api/pump-probe-v0/data/treat", json={**request, "format": "dat"})
                assert corrected.status_code == exported.status_code == 200
                actual = np.loadtxt(StringIO(exported.text))[1:, 1:].T
                expected = reconstructed_od(raw, "signed_all" if policy == "retain" else "signed_drop_zero")
                oracle_match = compare(expected, actual, 1e-14)
                saved_match = compare(saved, actual, 5.1e-5)
                info = corrected.get_json()
                removed = sum(info["shot_selection"]["removed_zero_slots"])
                assert oracle_match["pixel_class_mismatches"] == 0
                assert oracle_match["common_finite_pixels_exceeding_tolerance"] == 0
                if policy == "drop_whole_zero":
                    assert saved_match["pixel_class_mismatches"] == 0
                    assert saved_match["common_finite_pixels_exceeding_tolerance"] == 0
                records.append({
                    "zip_path": str(path), "source_sha256": fingerprint, "policy": policy,
                    "load_http": loaded.status_code, "treat_http": corrected.status_code,
                    "export_http": exported.status_code, "raw_groups": ";".join(info["raw_groups"]),
                    "removed_zero_slots": removed, "native_execution": False,
                    **{"oracle_" + key: value for key, value in oracle_match.items()},
                    **{"saved_dat_" + key: value for key, value in saved_match.items()},
                })
                print(path.name, policy, "oracle", oracle_match["max_common_finite_abs_error_od"],
                      "saved DAT", saved_match["max_common_finite_abs_error_od"], "removed", removed)
            assert path.read_bytes() == original
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    main()
