"""Build hash-pinned latest-frame update for the existing SuperVision XP site."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parents[1]
EXPECTED_PUBLISHER = [
    'adfb84e4fd5f30643aabddce193a7877d3f60cd88386666f04c236630a65e67e',
    'b57181cd29de396fae821fc1d826ebc657ae70d2d0914b02a36c71cb61b145cc']
EXPECTED_HELPER = '3f154eb9ecf96982dcbc89b51979e2187a4b09c1fe5bd10f154a19edba3093e4'
EXPECTED_ENTRY = '477860f5505ffd1094ac185b802a96c8a4e3ddbfd3986a5d2be492176c9ee34e'
LATEST_HELPER = 'bef72a8c0a4b7cc269e1694668464ba5c75164519687fee3b428552e7bd49bb7'


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    payload = {}
    for name in ('camera_latest.py', 'camera_stream_publisher.py'):
        raw = (REPO/'legacy/xp_acq_control/elyse_agent'/name).read_bytes().replace(b'\r\n', b'\n')
        (output/name).write_bytes(raw)
        payload[name] = hashlib.sha256(raw).hexdigest()
    source = REPO/'legacy/labview/supervision_telemetry/individual_helpers/camera/observer_v3/SUP_Camera_Queue_Latest.vi'
    if hashlib.sha256(source.read_bytes()).hexdigest() != LATEST_HELPER:
        raise RuntimeError('Native latest producer baseline changed')
    shutil.copy2(str(source), str(output/source.name))
    payload[source.name] = LATEST_HELPER
    manifest = dict(kind='SUPERVISION_LATEST_CAMERA', python_version='3.4',
                    files=payload, expected_publisher_sha256=EXPECTED_PUBLISHER,
                    expected_helper_sha256=EXPECTED_HELPER, expected_entry_sha256=EXPECTED_ENTRY,
                    initialization_invoked=False, hardware_commands_sent=False,
                    wrapper_capacity_verified=1, original_vi_changed=False,
                    synchronization_changed=False, live25Hz_qualified=False)
    raw = (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode('utf-8')
    (output/'manifest.json').write_bytes(raw)
    installer = (REPO/'tools/install_supervision_camera_latest.pyw').read_text(encoding='utf-8')
    installer = installer.replace('PAYLOAD_MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())
    (output/'APPLY_LATEST.pyw').write_bytes(installer.replace('\r\n', '\n').encode('utf-8'))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
