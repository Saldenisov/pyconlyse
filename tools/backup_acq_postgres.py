"""Consistent logical backup on F:; traverse the complete dump without executing it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from DeviceServers.control.elyse_acq.telemetry_archive import PostgresStore, utc


def backup(config, destination):
    destination = Path(destination).resolve()
    if not destination.is_relative_to(Path('F:/ELYSE_PostgreSQL/backups').resolve()) or destination.exists():
        raise ValueError('A new destination inside F:/ELYSE_PostgreSQL/backups is required')
    store = PostgresStore(config)
    before = store.summary()
    if not before['imports'] or any(row['state'] != 'COMPLETE' for row in before['imports']):
        raise RuntimeError('Historical import is incomplete; final backup refused')
    private = json.loads(Path(config).with_name('admin.json').read_text(encoding='utf-8'))
    environment = dict(os.environ, PGPASSWORD=private['password'])
    binaries = Path('F:/ELYSE_PostgreSQL/17.11/pgsql/bin')
    started = utc()
    subprocess.run([str(binaries / 'pg_dump.exe'), '-Fc', '-Z', '9', '--no-password',
                    '--host', private['host'], '--port', str(private['port']),
                    '--username', private['user'], '--dbname', store.config['dbname'],
                    '--file', str(destination)], env=environment, check=True)
    subprocess.run([str(binaries / 'pg_restore.exe'), '--list', str(destination)],
                   stdout=subprocess.DEVNULL, check=True)
    # Unlike --list, this reads/decompresses all archive data. No database target:
    # SQL is generated to the null stream, never executed against any cluster.
    subprocess.run([str(binaries / 'pg_restore.exe'), '--file=-', str(destination)],
                   stdout=subprocess.DEVNULL, check=True)
    with destination.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = dict(result='PASS', started_utc=started, verified_utc=utc(), path=str(destination),
                  bytes=destination.stat().st_size, sha256=digest, history_before_dump=before,
                  full_archive_decompression_verified=True, restore_into_database_tested=False,
                  live_database_not_stopped=True, same_disk_not_disaster_recovery=True,
                  hardware_commands_sent=False)
    destination.with_suffix(destination.suffix + '.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(backup(args.config, args.output)), flush=True)
