"""Finite passive acceptance: 27 banks, PostgreSQL equality, web freshness."""
import argparse
import datetime
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tango
from DeviceServers.control.elyse_acq.telemetry_archive import PostgresStore
from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS


def main(args):
    store = PostgresStore(args.config)
    device = tango.DeviceProxy('elyse/acquisition/telemetry')
    device.set_timeout_millis(3000)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    before = json.loads(device.read_attribute('archive_status_json').value)
    started = time.monotonic()
    counts, maximum_age, issues, matched = [], 0., [], 0
    pending_max = 0
    for index in range(args.samples):
        observed = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with opener.open('http://127.0.0.1:5000/api/elyse/acquisition/telemetry', timeout=5) as response:
                web = json.load(response)
            snapshot = web['snapshot']
            banks = snapshot['publications']
            archive = json.loads(device.read_attribute('archive_status_json').value)
            pending_max = max(pending_max, archive['pending'])
            if web['quality'] != 'FRESH' or set(banks) != set(BANKS) or archive['last_error']:
                raise ValueError(json.dumps(dict(quality=web['quality'], banks=len(banks),
                      stale=web.get('stale_banks'), errors=web.get('error_banks'), archive=archive)))
            maximum_age = max(maximum_age, *(bank['age_seconds'] for bank in banks.values()))
            counts.append(snapshot['received_this_process'])
            if index % 10 == 0:
                first = next(iter(banks.values()))
                uid = f"live:{first['relay_id']}:{first['message_id']}"
                deadline = time.monotonic() + 5
                while True:
                    with store.connect() as conn:
                        rows = conn.execute('SELECT bank,data,error FROM acq_archive_banks WHERE frame_uid=%s', (uid,)).fetchall()
                    if len(rows) == 27:
                        break
                    if time.monotonic() > deadline:
                        raise ValueError('Database commit did not catch up within 5 seconds')
                    time.sleep(.05)
                for bank, data, error in rows:
                    if data != banks[bank]['data'] or error != banks[bank]['error']:
                        raise ValueError('PostgreSQL/live bank content mismatch: ' + bank)
                matched += 1
        except Exception as error:
            issues.append(dict(utc=observed, error=type(error).__name__ + ': ' + str(error)))
        if (index + 1) % 30 == 0:
            print(json.dumps(dict(samples=index + 1, issues=len(issues), max_age=maximum_age,
                                  committed_matches=matched, pending_max=pending_max)), flush=True)
        time.sleep(max(0, started + index + 1 - time.monotonic()))
    after = json.loads(device.read_attribute('archive_status_json').value)
    success = (not issues and len(set(counts)) >= args.samples * .8
               and after['committed_this_process'] > before['committed_this_process'])
    report = dict(result='PASS' if success else 'FAIL', samples=args.samples,
                  unique_receipts=len(set(counts)), receiver_count_range=[min(counts), max(counts)] if counts else [],
                  max_bank_age_seconds=maximum_age, pending_max=pending_max,
                  full_27_bank_database_matches=matched, issues=issues, archive_before=before, archive_after=after,
                  hardware_commands_sent=False, xp_touched=False,
                  end_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)
    return 0 if success else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--samples', type=int, default=120)
    args = parser.parse_args()
    if not 30 <= args.samples <= 300:
        raise ValueError('Finite sample count must be 30..300')
    raise SystemExit(main(args))
