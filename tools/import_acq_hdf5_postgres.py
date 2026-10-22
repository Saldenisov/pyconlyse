"""Import only confirmed closed HDF5 archives. Never repair or modify originals."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from DeviceServers.control.elyse_acq.telemetry_archive import PostgresStore, utc


def verify_recorder_absent(status):
    # A reused PID is not the recorder. An inaccessible process is ambiguous.
    if os.name == 'nt' and status.get('pid'):
        import psutil
        try:
            argv = psutil.Process(int(status['pid'])).cmdline()
        except psutil.NoSuchProcess:
            argv = []
        except psutil.AccessDenied as error:
            raise RuntimeError('Recorder PID cannot be verified; refusing HDF5 access') from error
        if any(Path(arg).name == 'record_acq_telemetry_hdf5.py' for arg in argv):
            raise RuntimeError('Recorder PID still exists; refusing HDF5 access')


def require_closed(folder, *, allow_orphaned=False):
    status = json.loads((folder / 'status.json').read_text(encoding='utf-8'))
    orphaned = status.get('state') not in ('STOPPED', 'FAILED')
    if orphaned:
        if not allow_orphaned or os.name != 'nt' or status.get('state') != 'RUNNING' or not status.get('pid'):
            raise RuntimeError('Live or unconfirmed archive: refusing to open HDF5')
        updated = datetime.datetime.fromisoformat(status['updated_utc'].replace('Z', '+00:00'))
        if updated.tzinfo is None or (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds() < 60:
            raise RuntimeError('Orphan status is recent or unqualified; refusing HDF5 access')
        if Path(status['file']).resolve() != (folder / 'telemetry.h5').resolve():
            raise RuntimeError('Orphan file identity differs; refusing HDF5 access')
    verify_recorder_absent(status)
    return status


def import_folder(store, folder, *, batch_size=64, priority_since=None, allow_orphaned=False):
    folder = Path(folder).resolve()
    status = require_closed(folder, allow_orphaned=allow_orphaned)
    archive_id = status['recorder_id']
    import h5py
    # Orphan SWMR format may retain a writer flag. Read it without clearing flags,
    # and only after the explicit dead-recorder checks; never repair the source.
    with h5py.File(folder / 'telemetry.h5', 'r', swmr=status.get('state') == 'RUNNING') as archive:
        index_data, payload_data = archive['index'], archive['payload_utf8']
        committed = int(archive['committed_rows'][()])
        if committed > len(index_data):
            raise ValueError('Committed-row marker exceeds archive index')
        with store.connect(writer=True) as conn:
            conn.execute('INSERT INTO acq_archive_imports(archive_id,source_path,committed_rows,state) '
                         "VALUES (%s,%s,%s,'IMPORTING') ON CONFLICT (archive_id) DO NOTHING",
                         (archive_id, str(folder), committed))
            prior = conn.execute('SELECT source_path,committed_rows,imported_rows FROM acq_archive_imports '
                                 'WHERE archive_id=%s', (archive_id,)).fetchone()
            if prior[0] != str(folder) or prior[1] != committed:
                raise ValueError('Imported archive identity changed')
        start = prior[2]
        attributes = {}
        for key, value in archive.attrs.items():
            value = value.tolist() if hasattr(value, 'tolist') else value
            attributes[str(key)] = value.decode('utf-8') if isinstance(value, bytes) else value
        metadata = dict(file_attributes=attributes, final_status=status, source_path=str(folder))
        if status.get('state') == 'RUNNING':
            metadata['closure_qualification'] = 'explicit_orphan_import_original_recorder_absent_status_unchanged'
        store.write_records([dict(uid='hdf5meta:' + archive_id, kind='archive_metadata',
             provenance='hdf5_metadata', observed_utc=attributes.get('created_utc') or status['started_utc'],
             metadata=metadata)])
        if priority_since:
            import datetime
            import numpy as np
            cutoff = datetime.datetime.fromisoformat(priority_since.replace('Z', '+00:00'))
            if cutoff.tzinfo is None:
                raise ValueError('Priority timestamp requires timezone')
            marks = index_data.fields('observed_ns')[:committed]
            candidates = np.flatnonzero(marks >= int(cutoff.timestamp() * 1e9))
            start = max(start, int(candidates[0]) if len(candidates) else committed)
        for first in range(start, committed, batch_size):
            batch = []
            for row_index in range(first, min(first + batch_size, committed)):
                row = index_data[row_index]
                offset, length = int(row['offset']), int(row['length'])
                if offset + length > len(payload_data):
                    raise ValueError('Committed payload exceeds archive dataset')
                value = json.loads(payload_data[offset:offset + length].tobytes())
                kind = row['kind'].decode('ascii').rstrip('\0')
                observed = value.get('observed_utc') or value.get('utc')
                if not observed:
                    import datetime
                    observed = datetime.datetime.fromtimestamp(int(row['observed_ns']) / 1e9,
                                                               datetime.timezone.utc).isoformat()
                snapshot = value.get('snapshot') if kind == 'snapshot' else None
                record = dict(uid=f'hdf5:{archive_id}:{row_index}', observed_utc=observed,
                              kind=kind, provenance=f'hdf5:{archive_id}', original=value,
                              receiver_session=snapshot.get('receiver_session') if snapshot else None,
                              receiver_count=int(row['receiver_count']))
                if snapshot:
                    record['snapshot'] = snapshot
                batch.append(record)
            store.write_records(batch)
            count = min(first + batch_size, committed)
            if not priority_since:
                with store.connect(writer=True) as conn:
                    conn.execute("UPDATE acq_archive_imports SET imported_rows=GREATEST(imported_rows,%s),"
                                 "state=CASE WHEN GREATEST(imported_rows,%s)>=committed_rows THEN 'COMPLETE' ELSE 'IMPORTING' END,"
                                 'updated_utc=clock_timestamp() WHERE archive_id=%s', (count, count, archive_id))
            if first == start or count == committed or count % 4096 < batch_size:
                print(json.dumps(dict(utc=utc(), archive_id=archive_id, imported_rows=count,
                                      committed_rows=committed, priority_since=priority_since)), flush=True)
    return dict(archive_id=archive_id, committed_rows=committed, source_unmodified=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--priority-since')
    parser.add_argument('--allow-orphaned', action='store_true',
                        help='Explicitly allow old RUNNING status only after original Windows recorder PID is absent; never repair HDF5')
    parser.add_argument('folders', nargs='+', type=Path)
    args = parser.parse_args()
    store = PostgresStore(args.config)
    store.initialize()
    for folder in args.folders:
        if not 1 <= args.batch_size <= 512:
            raise ValueError('Batch size must be 1..512')
        print(json.dumps(import_folder(store, folder, batch_size=args.batch_size,
                                     priority_since=args.priority_since, allow_orphaned=args.allow_orphaned)), flush=True)
