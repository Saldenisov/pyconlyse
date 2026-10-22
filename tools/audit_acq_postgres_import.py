"""Read-only closed-file/database audit. No device or control connections."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from DeviceServers.control.elyse_acq.telemetry_archive import PostgresStore, utc
from tools.import_acq_hdf5_postgres import require_closed


def audit(store, folder, allow_orphaned=False):
    import h5py
    folder = Path(folder).resolve()
    status = require_closed(folder, allow_orphaned=allow_orphaned)
    archive_id = status['recorder_id']
    path = folder / 'telemetry.h5'
    before = path.stat()
    with h5py.File(path, 'r', swmr=status.get('state') == 'RUNNING') as archive, store.connect() as conn:
        conn.execute('SET LOCAL statement_timeout=60000')
        committed = int(archive['committed_rows'][()])
        index = archive['index'][:committed]
        kinds = Counter(bytes(row['kind']).decode('ascii').rstrip('\0') for row in index)
        rows = conn.execute('SELECT uid,kind FROM acq_archive_frames WHERE provenance=%s',
                            ('hdf5:' + archive_id,)).fetchall()
        assert {row[0] for row in rows} == {f'hdf5:{archive_id}:{i}' for i in range(committed)}, 'Frame coverage differs'
        assert Counter(row[1] for row in rows) == kinds, 'Frame kinds differ'
        ledger = conn.execute('SELECT committed_rows,imported_rows,state FROM acq_archive_imports WHERE archive_id=%s',
                              (archive_id,)).fetchone()
        assert ledger == (committed, committed, 'COMPLETE'), 'Import ledger incomplete'
        header = conn.execute('SELECT payload_zlib FROM acq_archive_frames WHERE uid=%s',
                              ('hdf5meta:' + archive_id,)).fetchone()
        assert header, 'Missing file metadata'
        assert json.loads(zlib.decompress(header[0]))['metadata']['final_status'] == status, 'Original status differs'
        # Deterministic spread, plus first/last occurrence of every event kind.
        selected = {int(i * (committed - 1) / 20) for i in range(21)} if committed else set()
        for kind in kinds:
            occurrences = [i for i, row in enumerate(index) if bytes(row['kind']).decode('ascii').rstrip('\0') == kind]
            selected.update((occurrences[0], occurrences[-1]))
        verified_banks = 0
        for i in sorted(selected):
            row = index[i]
            offset, length = int(row['offset']), int(row['length'])
            original = json.loads(archive['payload_utf8'][offset:offset + length].tobytes())
            uid = f'hdf5:{archive_id}:{i}'
            payload = conn.execute('SELECT payload_zlib FROM acq_archive_frames WHERE uid=%s', (uid,)).fetchone()[0]
            imported = json.loads(zlib.decompress(payload))
            assert imported['original'] == original, f'Original record differs: {i}'
            publications = original.get('snapshot', {}).get('publications', {}) if imported['kind'] == 'snapshot' else {}
            banks = conn.execute('SELECT b.bank,b.data,b.error,b.stale,b.age_seconds,b.source_session,'
                                 'b.source_sequence,b.source_seconds_1904,b.producer_kind,t.definition '
                                 'FROM acq_archive_banks b LEFT JOIN acq_archive_types t ON t.digest=b.type_digest '
                                 'WHERE b.frame_uid=%s', (uid,)).fetchall()
            assert {b[0] for b in banks} == set(publications), f'Bank coverage differs: {i}'
            for name, data, error, stale, age, session, sequence, seconds, producer, definition in banks:
                source = publications[name]
                assert (data, error, stale, age, session, producer, definition) == (
                    source.get('data'), source.get('error', {}), source.get('stale') is not False,
                    source.get('age_seconds'), source.get('session_id'), source.get('producer_kind'), source.get('lv_type'))
                expected_sequence = source.get('sequence')
                expected_seconds = source.get('source_seconds_1904')
                assert sequence == (Decimal(str(expected_sequence)) if expected_sequence is not None else None)
                assert seconds == (Decimal(str(expected_seconds)) if expected_seconds is not None else None)
                verified_banks += 1
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'Input changed during audit'
    return dict(archive_id=archive_id, path=str(path), committed_rows=committed,
                kinds=dict(kinds), verified_records=len(selected), verified_banks=verified_banks,
                file_bytes=after.st_size, file_sha256=digest, original_status=status['state'],
                verification='complete frame identity/kind coverage; sampled original and typed bank equality',
                source_changed_during_audit=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-orphaned', action='store_true')
    parser.add_argument('folders', nargs='+', type=Path)
    args = parser.parse_args()
    store = PostgresStore(args.config)
    results = []
    for folder in args.folders:
        result = audit(store, folder, args.allow_orphaned)
        results.append(result)
        print(json.dumps(result), flush=True)
    with store.connect() as conn:
        assert conn.execute('SELECT count(*) FROM acq_archive_frames WHERE provenance=%s', ('test_fixture',)).fetchone()[0] == 0
    report = dict(result='PASS', utc=utc(), archives=results, hardware_commands_sent=False,
                  production_test_fixture_frames=0)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
