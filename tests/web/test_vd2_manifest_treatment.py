"""Actual synthetic HIS → H5 → SAM cleaning → OD DAT, including shared noise."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import numpy as np

from tests.web.test_treatment_queue_api import queue_client
from tests.unit.test_vd2_project_manifest import two_samples
import treatment_api as api
from vd2_project_manifest import MANIFEST_NAME, fingerprint, inspect_project, load_manifest, record_project_treatment


def test_manifest_runs_two_private_cleaned_recipes_and_preserves_sources(queue_client, monkeypatch):
    client, root, headers = queue_client
    two_samples(root)
    monkeypatch.setattr(api, "_cpu_executor", lambda count: ThreadPoolExecutor(max_workers=count))
    sources = {str(path): fingerprint(path) for path in root.rglob('*') if path.suffix in {'.his', '.h5'}}
    before = api.session_store.snapshot("queue-contract")
    payload = {"manifest_path": str(root / MANIFEST_NAME)}
    response = client.post('/api/treatment/manifest/vd2', json=payload, headers=headers)
    assert response.status_code == 200, response.get_json()
    assert all(row['ready'] for row in response.get_json()['manifest']['samples'])
    response = client.post('/api/treatment/manifest/vd2/queue', json={**payload, 'samples': ['sample 1', 'sample 2']}, headers=headers)
    assert response.status_code == 200, response.get_json()
    deadline = time.monotonic() + 15
    while api.treatment_queue_store.snapshot('queue-contract')['running'] and time.monotonic() < deadline:
        time.sleep(.02)
    jobs = api.treatment_queue_store.snapshot('queue-contract')['jobs']
    assert len(jobs) == 2
    assert [job['status'] for job in jobs] == ['completed', 'completed'], jobs
    for name, job in zip(('sample 1', 'sample 2'), jobs):
        assert job['recipe']['cleaning']['state'] == 'pending'
        assert set(job['preparation']['cleaned']) == {'NOISE', 'BASE', 'ABS'}
        values = np.loadtxt(root / name / f'{name}.dat', delimiter='\t')[1:, 1:]
        # Existing DAT format rounds OD to four decimal places.
        np.testing.assert_allclose(values, -np.log10(.8), atol=5e-5)
    assert jobs[1]['recipe']['provenance']['vd2_project']['bruit_reused'] is True
    assert api.session_store.snapshot('queue-contract') == before
    assert all(fingerprint(path) == before for path, before in sources.items())
    project = load_manifest(root / MANIFEST_NAME)
    for name in ('sample 1', 'sample 2'):
        receipt = project['samples'][name]['treatments'][0]
        assert receipt['dat']['sha256'] == fingerprint(root / name / f'{name}.dat')['sha256']
        assert receipt['artifact_ids']['NOISE'] == project['samples'][name]['bruit_reference']


def test_manifest_modified_input_blocks_entire_selected_batch(queue_client):
    client, root, headers = queue_client
    two_samples(root)
    (root / 'sample 2/ABS.h5').write_bytes(b'changed')
    response = client.post('/api/treatment/manifest/vd2/queue', json={
        'manifest_path': str(root / MANIFEST_NAME), 'samples': ['sample 1', 'sample 2']}, headers=headers)
    assert response.status_code == 400
    assert api.treatment_queue_store.snapshot('queue-contract')['jobs'] == []
    assert not list(root.rglob('*.dat'))


def test_manifest_new_only_checks_dat_provenance_and_saves_in_project(queue_client):
    client, root, headers = queue_client
    two_samples(root)
    path = root / MANIFEST_NAME
    plan = inspect_project(path)
    first = root / 'sample 1.dat'
    first.write_text('Existing verified result', encoding='utf-8')
    record_project_treatment({
        'manifest_path': str(path), 'project_id': plan['project_id'], 'sample': 'sample 1',
        'artifact_ids': plan['samples'][0]['artifact_ids'],
    }, {'save_path': str(first)}, {})
    payload = {'manifest_path': str(path), 'samples': ['sample 1', 'sample 2'], 'mode': 'new', 'clean': False}
    response = client.post('/api/treatment/manifest/vd2/queue', json=payload, headers=headers)
    assert response.status_code == 200, response.json
    assert response.json['skipped_samples'] == ['sample 1']
    assert len(response.json['queue_jobs']) == 1
    deadline = time.monotonic() + 15
    while api.treatment_queue_store.snapshot('queue-contract')['running'] and time.monotonic() < deadline:
        time.sleep(.02)
    jobs = api.treatment_queue_store.snapshot('queue-contract')['jobs']
    assert [job['status'] for job in jobs] == ['completed'], jobs
    assert (root / 'sample 2.dat').is_file()
    assert first.read_text(encoding='utf-8') == 'Existing verified result'
    current = client.post('/api/treatment/manifest/vd2/queue', json=payload, headers=headers)
    assert current.json['skipped_samples'] == ['sample 1', 'sample 2']
    assert current.json['queue_jobs'] == []
    first.write_text('Replaced result', encoding='utf-8')
    refreshed = client.post('/api/treatment/manifest/vd2', json=payload, headers=headers)
    assert refreshed.json['manifest']['samples'][0]['result_path'] is None


def test_tree_batch_saves_each_folder_under_its_own_name(queue_client):
    client, root, headers = queue_client
    two_samples(root)
    noise = (root / 'sample 1/BRUIT.h5').read_bytes()
    (root / 'sample 2/BRUIT.h5').write_bytes(noise)
    response = client.post('/api/treatment/queue/folder-set', json={
        'folder_paths': [str(root / 'sample 1'), str(root / 'sample 2')],
        'output_naming': 'sample', 'exp_type': 'ABS+BASE+NOISE',
        'convert': False, 'clean': False, 'calculate': True,
    }, headers=headers)
    assert response.status_code == 200, response.json
    deadline = time.monotonic() + 15
    while api.treatment_queue_store.snapshot('queue-contract')['running'] and time.monotonic() < deadline:
        time.sleep(.02)
    jobs = api.treatment_queue_store.snapshot('queue-contract')['jobs']
    assert [job['status'] for job in jobs] == ['completed', 'completed'], jobs
    for name, job in zip(('sample 1', 'sample 2'), jobs):
        assert job['saved']['save_path'] == str(root / f'{name}.dat')
        assert (root / f'{name}.dat').is_file()
        assert job['preparation']['folder_set']['map_policy'] == 'selected_maps'


def test_tree_clean_then_calculate_preserves_manifest_inputs(queue_client, monkeypatch):
    client, root, headers = queue_client
    two_samples(root)
    monkeypatch.setattr(api, "_cpu_executor", lambda count: ThreadPoolExecutor(max_workers=count))
    sample = root / 'sample 1'
    originals = {path: fingerprint(path) for path in sample.glob('*.h5')}
    request = {'folder_paths': [str(sample)], 'output_naming': 'sample'}

    def run_action(**flags):
        response = client.post('/api/treatment/queue/folder-set', json={**request, **flags}, headers=headers)
        assert response.status_code == 200, response.json
        deadline = time.monotonic() + 15
        while api.treatment_queue_store.snapshot('queue-contract')['running'] and time.monotonic() < deadline:
            time.sleep(.02)
        job = api.treatment_queue_store.snapshot('queue-contract')['jobs'][-1]
        assert job['status'] == 'completed', job
        return job['preparation']['folder_set']

    clean = run_action(convert=True, clean=True, calculate=False)
    assert all(fingerprint(path) == before for path, before in originals.items())
    assert all(row['ready'] for row in inspect_project(root / MANIFEST_NAME)['samples'])
    calculated = run_action(convert=False, clean=False, calculate=True)
    for role, output in clean['cleaned'].items():
        assert Path(output['output_path']) not in originals
        assert calculated['cached_files'][role]['source_path'] == output['output_path']
    assert (root / 'sample 1.dat').is_file()


def test_batch_output_reservation_is_atomic(queue_client):
    _, root, _ = queue_client
    store = api.treatment_queue_store
    source = lambda name: {'output': {'path': str(root / name)}}
    store.enqueue('other-user', source('second.dat'))
    import pytest
    with pytest.raises(ValueError, match='reserved'):
        store.enqueue_batch('queue-contract', [source('first.dat'), source('second.dat')])
    assert store.snapshot('queue-contract')['jobs'] == []
    # The first output was not reserved by a partially enqueued batch.
    assert store.enqueue('third-user', source('first.dat'))['status'] == 'queued'


def test_copy_as_path_quotes_load_manifest_and_return_project_folder_without_changing_global_root(queue_client):
    client, root, headers = queue_client
    two_samples(root)
    allowed_before = api.get_allowed_root()
    response = client.post('/api/treatment/manifest/vd2', headers=headers,
                           json={'manifest_path': f'  "{root / MANIFEST_NAME}"  '})
    assert response.status_code == 200, response.json
    assert response.json['manifest']['project_folder'] == str(root)
    assert response.json['manifest']['manifest_path'] == str(root / MANIFEST_NAME)
    assert api.get_allowed_root() == allowed_before
    assert api.treatment_queue_store.snapshot('queue-contract')['jobs'] == []


def test_quotes_do_not_bypass_the_existing_treatment_root_boundary(queue_client):
    client, root, headers = queue_client
    response = client.post('/api/treatment/manifest/vd2', headers=headers,
                           json={'manifest_path': f'"{root.parent / MANIFEST_NAME}"'})
    assert response.status_code == 400
    assert 'outside the allowed treatment root' in response.json['error']
