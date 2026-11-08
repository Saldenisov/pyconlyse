"""Build an offline Python 3.4 telemetry-only artifact and a private relay key.

The generated artifact never contains a driver, NI backend or hardware command
router. Key contents are not logged. Existing destinations are never replaced.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "shared_state_receiver.pyw",
    "config.shared-state.json",
    "elyse_agent/__init__.py",
    "elyse_agent/errors.py",
    "elyse_agent/protocol.py",
    "elyse_agent/supervision_wire.py",
    "elyse_agent/telemetry_relay.py",
    "elyse_agent/labview_telemetry.py",
    "elyse_agent/shared_state.py",
    "elyse_agent/shared_state_receiver.py",
)


def build(destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    package = destination / "ACQ_SharedState_Python34_20261013"
    package.mkdir()
    entries = []
    source = ROOT / "legacy" / "xp_acq_agent"
    for name in FILES:
        data = (source / name).read_bytes()
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entries.append(
            dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        )
    key_file = package / "shared-state-relay.key"
    key_file.write_bytes(binascii.hexlify(os.urandom(32)) + b"\n")
    archive = destination / "ACQ_SharedState_Python34_20261013.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for name in FILES + ("shared-state-relay.key",):
            output.write(package / name, "ACQ_SharedState_Python34_20261013/" + name)
    manifest = dict(
        package=str(package),
        archive=str(archive),
        private_key_file=str(key_file),
        files=entries,
        receiver="127.0.0.1:8766",
        everest="10.20.30.202:8767",
        producer_kind="copied_acquisition",
        hardware_actions=False,
        storage="latest pending snapshot plus one in-flight retry; RAM only",
        deployment_complete=False,
        native_worker_complete=False,
    )
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.output)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "files"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
