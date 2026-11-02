"""Offline fixture benchmark; no Tango, network, hardware or archive access."""
import copy
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from DeviceServers.control.elyse_acq import telemetry_sink as after
from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS
from legacy.xp_acq_agent.elyse_agent.telemetry_relay import sign

old = subprocess.check_output(['git', 'show', 'f7348836:DeviceServers/control/elyse_acq/telemetry_sink.py'], cwd=ROOT)
before = types.ModuleType('sink_before')
exec(compile(old, 'sink_before.py', 'exec'), before.__dict__)
KEY = b'offline-fixture-only-not-a-production-key'
body = dict(schema_version=1, relay_id='a' * 32, message_id=1,
    received_utc_on_xp='2026-11-02T17:00:00Z', age_seconds_on_xp=.1, hardware_writes=False,
    packet=dict(session_id='offline-copy-benchmark', publication='ACQ_SHARED_STATE', sequence=0,
        source_seconds_1904=3870000000.25, producer_kind='fixture', error=dict(status=False, code=0, source=''),
        data=dict(snapshot_version=1, capture_kind='sequential_local_controls',
            timestamp_origin='xp_receipt_not_card_sample', banks=[
                dict(publication=name, data=[i / 10. for i in range(64)],
                     lv_type=dict(type='LvVariant', contained_type=dict(type='Array', element=dict(type='DBL'))),
                     error=dict(status=False, code=0, source='')) for name in BANKS])))
results = {}
snapshots = []
for label, module in [('before', before), ('after', after)]:
    timings = []
    for repeat in range(3):
        store = module.TelemetrySinkStore(KEY, clock=lambda: 10.)
        try:
            for index in range(30):
                body['message_id'] = index + 1
                body['packet']['sequence'] = index
                signed = dict(body=copy.deepcopy(body), nonce='b' * 32)
                signed['signature'] = sign(KEY, 'ACQ-TELEMETRY-REQUEST-1', signed)
                started = time.perf_counter()
                store.accept(signed)
                timings.append(time.perf_counter() - started)
            snap = store.snapshot()['publications']
            for value in snap.values():
                value.pop('received_utc_on_everest')
            snapshots.append(snap)
        finally:
            store.close()
    results[label] = dict(samples=len(timings), median_ms=statistics.median(timings) * 1000,
        mean_ms=statistics.mean(timings) * 1000, max_ms=max(timings) * 1000)
assert all(value == snapshots[0] for value in snapshots)
results['identical_27_bank_output'] = True
results['fixture_bytes'] = len(json.dumps(body))
results['median_speedup'] = results['before']['median_ms'] / results['after']['median_ms']
Path(__file__).with_suffix('.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results))
