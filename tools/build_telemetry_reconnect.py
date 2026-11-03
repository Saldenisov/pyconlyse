"""Stage persistent telemetry updates; no deployment, VI execution or keys."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASELINE = {
    'telemetry_relay.py': '9e8a11601cf22f5e9bd28f46a2a733e2cc1008c839199e9fe838a1bc68f1d8e3',
    'shared_state_receiver.py': 'a2c7908ae8453bae255e833cad3e793b993623d3669bdda3f4ab08dca197b46a',
    'camera_stream.py': '1d6ccdd8b6305f03e7b1127ee681490957d595d2a1df9ae534cd058ec6941446',
    'camera_stream_publisher.py': 'c811e6de054056bb2b73b4b185beefbf2f3659269cc95275bb26d930d5fb2a02',
}


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, before in BASELINE.items():
        raw = (ROOT/'legacy/xp_acq_control/elyse_agent'/name).read_bytes().replace(b'\r\n', b'\n')
        compile(raw, name, 'exec')
        (output/name).write_bytes(raw)
        files[name] = dict(before_sha256=before, after_sha256=hashlib.sha256(raw).hexdigest())
    everest_files = {}
    for name in ('telemetry_sink.py', 'DS_AcqTelemetry.py'):
        target = output/'everest'/name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(ROOT/'DeviceServers/control/elyse_acq'/name, target)
        everest_files[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = dict(schema_version=1, kind='TELEMETRY_PERSISTENT_RECONNECT_20261103', files=files,
        everest_files=everest_files,
        roles=dict(acquisition=['telemetry_relay.py', 'shared_state_receiver.py'], supervision=list(BASELINE)),
        hardware_commands_sent=False, initialize_invoked=False, vi_files_changed=False)
    raw = (json.dumps(manifest, sort_keys=True, indent=2)+'\n').encode('utf-8')
    (output/'manifest.json').write_bytes(raw)
    installer = (ROOT/'tools/install_telemetry_reconnect.py').read_text(encoding='utf-8')
    installer = installer.replace('PAYLOAD_MANIFEST_SHA256', hashlib.sha256(raw).hexdigest())
    (output/'apply_xp.py').write_bytes(installer.replace('\r\n', '\n').encode('utf-8'))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
