"""Session-isolated SK-Ana jobs over existing Python kernels; no device/file I/O."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
from threading import Event, RLock
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from flask import Blueprint, current_app, jsonify, request, send_file
from mutation_auth import install_mutation_auth

skana_api = Blueprint('skana_api', __name__, url_prefix='/api/treatment/skana')
install_mutation_auth(skana_api, protected_get_endpoints=('dataset', 'job_status', 'export_result'))
MAX_CELLS = 2_000_000
MAX_BODY = 16 * 1024 * 1024
RETENTION = 3600


def fingerprint(data):
    digest = sha256()
    for array in (data.matrix, data.times, data.wavelengths, data.delay_ids):
        digest.update(np.ascontiguousarray(array, dtype='<f8').tobytes())
    digest.update(str(data.time_unit).encode('utf-8'))
    return digest.hexdigest()


def preview(matrix, data, limit=128):
    rows = np.unique(np.linspace(0, len(data.times) - 1, min(limit, len(data.times))).astype(int))
    cols = np.unique(np.linspace(0, len(data.wavelengths) - 1, min(limit, len(data.wavelengths))).astype(int))
    return dict(z=np.asarray(matrix)[np.ix_(rows, cols)].tolist(), times=data.times[rows].tolist(),
                wavelengths=data.wavelengths[cols].tolist(),
                downsampled=len(rows) < len(data.times) or len(cols) < len(data.wavelengths))


def dataset_payload(data, source):
    if data is None:
        return dict(ready=False, source=source, label='Calculate OD first, or import a numeric matrix.')
    result = dict(ready=True, source=source, label=data.source, shape=list(data.matrix.shape),
                time_unit=data.time_unit, signal_unit=data.signal_unit, times=data.times.tolist(),
                wavelengths=data.wavelengths.tolist(), preview=preview(data.matrix, data), fingerprint=fingerprint(data))
    if source == 'import':
        result['warnings'] = ['SK-Ana sorts coordinate axes and replaces invalid/nonfinite signal cells with zero during text import.']
    return result


@dataclass
class Job:
    session: str
    data: object
    source: str
    method: str
    options: dict
    fingerprint: str
    id: str = field(default_factory=lambda: uuid4().hex)
    created: float = field(default_factory=monotonic)
    status: str = 'queued'
    cancel: Event = field(default_factory=Event)
    result: dict | None = None
    error: str = ''
    future: object = None
    finished_at: float | None = None


class Workspace:
    def __init__(self):
        self.lock = RLock()
        self.jobs = {}
        self.imports = {}
        # Existing kinetic LSODA solver is not reentrant. One worker also bounds
        # CPU/memory use and prevents concurrent BLAS fits blocking Web threads.
        self.executor = None

    def prune(self):
        now = monotonic()
        self.jobs = {k: v for k, v in self.jobs.items()
                     if v.status in ('queued', 'running') or now - (v.finished_at or v.created) < RETENTION}
        self.imports = {k: v for k, v in self.imports.items() if now - v[0] < RETENTION}

    def imported(self, session):
        with self.lock:
            self.prune()
            value = self.imports.get(session)
            return value[1] if value else None

    def save_import(self, session, data):
        with self.lock:
            self.prune()
            if session not in self.imports and len(self.imports) >= 8:
                raise RuntimeError('SK-Ana import capacity reached; retry after old sessions expire.')
            self.imports[session] = (monotonic(), data)

    def get(self, session, job_id):
        with self.lock:
            self.prune()
            job = self.jobs.get(job_id)
            if not job or job.session != session:
                raise LookupError('SK-Ana job not found in this treatment session.')
            return job

    def latest(self, session, source, identity):
        with self.lock:
            self.prune()
            jobs = [job for job in self.jobs.values() if job.session == session
                    and job.source == source and job.fingerprint == identity]
            return max(jobs, key=lambda j: j.created) if jobs else None

    def start(self, session, data, source, method, options):
        with self.lock:
            self.prune()
            if any(j.session == session and j.status in ('queued', 'running') for j in self.jobs.values()):
                raise RuntimeError('An analysis is already running in this treatment session.')
            # Retain at most two finished results per session; never discard work
            # from another session merely to admit a new request.
            finished = sorted((j for j in self.jobs.values() if j.session == session
                               and j.status not in ('queued', 'running')), key=lambda j: j.created)
            for old in finished[:-1]:
                del self.jobs[old.id]
            if len(self.jobs) >= 6:
                raise RuntimeError('SK-Ana job capacity reached; retry after previous jobs expire.')
            job = Job(session, data, source, method, options, fingerprint(data))
            self.jobs[job.id] = job
            if self.executor is None:
                self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='skana-analysis')
            job.future = self.executor.submit(self.run, job)
            return job

    def run(self, job):
        with self.lock:
            if job.cancel.is_set():
                job.status = 'cancelled'
                job.data = None
                job.finished_at = monotonic()
                return
            job.status = 'running'
        try:
            from utilities.skana import analyze
            result = analyze(job.data, job.method, job.options, cancel=job.cancel.is_set)
            result.update(requested_options=job.options, input_fingerprint=job.fingerprint, input_source=job.source)
            # Only strict JSON results enter the cache/export boundary.
            json.dumps(result, allow_nan=False)
            with self.lock:
                if job.cancel.is_set():
                    job.status = 'cancelled'
                else:
                    job.result = result
                    job.status = 'completed'
        except Exception as exc:
            with self.lock:
                job.status = 'cancelled' if job.cancel.is_set() else 'failed'
                job.error = '' if job.cancel.is_set() else str(exc)[:1000]
        finally:
            with self.lock:
                job.finished_at = monotonic()
                if job.status != 'completed':
                    job.data = None


def workspace():
    app = current_app._get_current_object()
    # Flask initializes this once before admitting jobs; app context is not used
    # by worker threads. No background process or external runtime is launched.
    with _workspace_lock:
        return app.extensions.setdefault('skana_workspace', Workspace())


_workspace_lock = RLock()


def session_id():
    from treatment_api import _current_session_id
    return _current_session_id()


def response(payload, session, status=200):
    from treatment_api import _json_response
    return _json_response(dict(success=True, **payload), session, status)


def source_data(session, source):
    if source == 'import':
        return workspace().imported(session)
    if source != 'od':
        raise ValueError('Source must be od or import.')
    from treatment_api import treatment_service
    from utilities.skana import from_measurement
    measurement = treatment_service.get_skana_result(session)
    return from_measurement(measurement) if measurement is not None else None


def json_body():
    if request.mimetype != 'application/json':
        raise ValueError('application/json required.')
    raw = request.stream.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError('SK-Ana request exceeds 16 MiB.')
    def invalid_constant(value):
        raise ValueError('Nonfinite JSON values are not permitted.')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    value = json.loads(raw, parse_constant=invalid_constant, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object.')
    return value


@skana_api.after_request
def no_cache(result):
    result.headers['Cache-Control'] = 'no-store'
    result.headers['X-Content-Type-Options'] = 'nosniff'
    return result


@skana_api.errorhandler(ValueError)
def invalid_request(error):
    return jsonify(success=False, error=str(error)), 400


@skana_api.errorhandler(LookupError)
def not_found(error):
    return jsonify(success=False, error=str(error)), 404


@skana_api.errorhandler(RuntimeError)
def conflict(error):
    return jsonify(success=False, error=str(error)), 409


@skana_api.get('/dataset')
def dataset():
    source = request.args.get('source', 'od')
    sid = session_id()
    data = source_data(sid, source)
    metadata = dataset_payload(data, source)
    latest = workspace().latest(sid, source, metadata['fingerprint']) if data is not None else None
    if latest:
        with workspace().lock:
            metadata['latest_job'] = job_payload(latest, False)['job']
    else:
        metadata['latest_job'] = None
    return response(dict(dataset=metadata, latest_job=metadata['latest_job']), sid)


@skana_api.post('/import')
def import_matrix():
    body = json_body()
    if set(body) - {'text', 'filename', 'time_unit', 'orientation'}:
        raise ValueError('Unknown matrix import option.')
    text, filename = body.get('text'), str(body.get('filename', 'matrix.csv'))
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Numeric matrix text is required.')
    orientation = {'time_rows': 'wxd', 'wavelength_rows': 'dxw'}.get(body.get('orientation', 'time_rows'))
    if orientation is None:
        raise ValueError('Choose time_rows or wavelength_rows orientation.')
    from skana import read_matrix
    from utilities.skana import Dataset
    parsed = read_matrix(text, name=Path(filename.replace('\\', '/')).name, orientation=orientation)
    if parsed.matrix.size > MAX_CELLS:
        raise ValueError('Matrix exceeds 2 million cells; select or compress before import.')
    data = Dataset(parsed.matrix, parsed.time, parsed.wavelength, time_unit=str(body.get('time_unit') or '??'),
                   signal_unit='input signal', source=parsed.name)
    sid = session_id()
    workspace().save_import(sid, data)
    payload = dataset_payload(data, 'import')
    return response(dict(dataset=payload), sid)


def job_payload(job, include_result=True):
    value = dict(id=job.id, status=job.status, method=job.method, source=job.source,
                 fingerprint=job.fingerprint, cancel_requested=job.cancel.is_set(), error=job.error)
    payload = dict(job=value)
    if include_result and job.status == 'completed' and job.result is not None:
        result = {k: v for k, v in job.result.items() if k not in ('reconstruction', 'residuals', 'data')}
        selected = SimpleNamespace(times=np.asarray(job.result['times']), wavelengths=np.asarray(job.result['wavelengths']))
        result.update(data_preview=preview(job.result['data'], selected),
                      model_preview=preview(job.result['reconstruction'], selected),
                      residual_preview=preview(job.result['residuals'], selected), fingerprint=job.fingerprint)
        payload['result'] = result
    return payload


@skana_api.post('/jobs')
def start_job():
    body = json_body()
    if set(body) - {'source', 'fingerprint', 'method', 'options'}:
        raise ValueError('Unknown analysis request field.')
    method = body.get('method')
    if method not in ('svd', 'mcr_als', 'target'):
        raise ValueError('Choose svd, mcr_als or target analysis.')
    options = body.get('options', {})
    if not isinstance(options, dict) or len(json.dumps(options, allow_nan=False)) > 65536:
        raise ValueError('Analysis options must be a bounded JSON object.')
    sid, source = session_id(), body.get('source', 'od')
    data = source_data(sid, source)
    if data is None:
        raise ValueError('Calculate OD first or import a matrix into SK-Ana.')
    if not body.get('fingerprint') or body['fingerprint'] != fingerprint(data):
        raise RuntimeError('Input matrix changed; reload it before starting analysis.')
    job = workspace().start(sid, data, source, method, options)
    return response(job_payload(job, False), sid, 202)


@skana_api.get('/jobs/<job_id>')
def job_status(job_id):
    sid = session_id()
    store = workspace()
    job = store.get(sid, job_id)
    with store.lock:
        return response(job_payload(job), sid)


@skana_api.post('/jobs/<job_id>/cancel')
def cancel_job(job_id):
    sid = session_id()
    store = workspace()
    job = store.get(sid, job_id)
    with store.lock:
        if job.status in ('queued', 'running'):
            job.cancel.set()
            if job.future.cancel():
                job.status, job.data = 'cancelled', None
                job.finished_at = monotonic()
        return response(job_payload(job, False), sid)


@skana_api.get('/jobs/<job_id>/export')
def export_result(job_id):
    job = workspace().get(session_id(), job_id)
    if job.status != 'completed' or job.result is None:
        raise RuntimeError('A completed analysis is required for export.')
    fmt = request.args.get('format', 'json')
    if fmt == 'json':
        output = BytesIO(json.dumps(job.result, ensure_ascii=False, allow_nan=False).encode('utf-8'))
        return send_file(output, mimetype='application/json', as_attachment=True, download_name=f'skana-{job.id}.json')
    if fmt != 'csv':
        raise ValueError('Export format must be json or csv.')
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, values in (('kinetics', job.result['concentrations']), ('spectra', job.result['spectra'])):
            axis = job.result['times'] if name == 'kinetics' else job.result['wavelengths']
            array = np.column_stack((axis, values))
            csv = StringIO()
            header = ('time' if name == 'kinetics' else 'wavelength') + ',' + ','.join(
                f'component_{i + 1}' for i in range(array.shape[1] - 1))
            np.savetxt(csv, array, delimiter=',', header=header, comments='')
            archive.writestr(name + '.csv', csv.getvalue())
        for name, values in (('data', job.data.matrix), ('model', job.result['reconstruction']), ('residuals', job.result['residuals'])):
            if name == 'data':
                values = job.result['data']
            array = np.column_stack((job.result['times'], np.asarray(values)))
            array = np.vstack((np.r_[0, job.result['wavelengths']], array))
            csv = StringIO()
            np.savetxt(csv, array, delimiter=',')
            archive.writestr(name + '.csv', csv.getvalue())
        metadata = {k: v for k, v in job.result.items() if k not in
                    ('concentrations', 'spectra', 'reconstruction', 'residuals', 'data', 'times', 'wavelengths')}
        archive.writestr('metadata.json', json.dumps(metadata, allow_nan=False, ensure_ascii=False))
    output.seek(0)
    return send_file(output, mimetype='application/zip', as_attachment=True, download_name=f'skana-{job.id}.zip')
