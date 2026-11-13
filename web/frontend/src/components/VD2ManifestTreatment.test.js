import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import VD2ManifestTreatment from './VD2ManifestTreatment';
import { postTreatment, fetchTreatmentQueue } from '../api/treatmentClient';

jest.mock('../api/treatmentClient', () => ({ postTreatment: jest.fn(), fetchTreatmentQueue: jest.fn() }));
jest.mock('../TopSection', () => ({
  SelectionHeatmap: ({ onReference }) => <button type="button" onClick={() => onReference({ start: 5, stop: 24 })}>Mark rows</button>,
}));
const path = 'E:\\DATA_VD2\\2026\\day\\project\\vd2-manifest.json';
const manifest = { manifest_path: path, samples: [
  { name: 'sample1', ready: true, bruit_sample: 'sample1', bruit_reused: false },
  { name: 'sample2', ready: true, bruit_sample: 'sample1', bruit_reused: true },
  { name: 'partial', ready: false, error: 'Missing completed ABSORPTION' },
] };
beforeEach(() => { postTreatment.mockReset(); fetchTreatmentQueue.mockReset(); window.localStorage.clear(); });

test('loading a manifest reviews ready and incomplete samples without starting work', async () => {
  postTreatment.mockResolvedValue({ manifest });
  render(<VD2ManifestTreatment initialManifest={path} />);
  expect(await screen.findByText('sample2')).toBeInTheDocument();
  expect(screen.getByText(/Missing completed ABSORPTION/)).toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: /sample2/ })).toBeChecked();
  expect(postTreatment).toHaveBeenCalledTimes(1);
  expect(postTreatment.mock.calls[0].slice(1)).toEqual(['/api/treatment/manifest/vd2', { manifest_path: path }]);
});

test('processing queues selected samples with cleaning enabled and displays DAT result', async () => {
  const source = 'sample2/ABS.h5';
  postTreatment.mockResolvedValueOnce({ manifest })
    .mockResolvedValueOnce({ selection: { spectral_reference_source: source } })
    .mockResolvedValueOnce({ queue: {
    running: false, pending_count: 0, jobs: [{ job_id: 'job', status: 'completed', phase: 'saved', label: 'sample2', saved: { save_path: 'sample2.dat' } }],
  } });
  render(<VD2ManifestTreatment initialManifest={path} />);
  await screen.findByText('sample2');
  fireEvent.click(screen.getAllByRole('checkbox')[0]);
  expect(screen.getByRole('button', { name: 'Calculate new only' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Draw ABS window · sample2' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Mark rows' }));
  fireEvent.click(screen.getByRole('button', { name: 'Calculate new only' }));
  await waitFor(() => expect(postTreatment).toHaveBeenCalledTimes(3));
  expect(postTreatment.mock.calls[2].slice(1)).toEqual(['/api/treatment/manifest/vd2/queue', {
    manifest_path: path, samples: ['sample2'], mode: 'new', clean: true, calc_mode: 'matched_spectral_sum', angle_threshold: 1, surface_threshold: 1,
    spectral_references: { sample2: { source, start: 5, stop: 24 } },
  }]);
  expect(await screen.findByLabelText('Manifest treatment jobs')).toHaveTextContent('sample2 · completed');
});

test('invalid or changed inputs remain visible and cannot be calculated', async () => {
  postTreatment.mockRejectedValue(new Error('Manifest input changed: BRUIT.h5'));
  render(<VD2ManifestTreatment initialManifest={path} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Manifest input changed: BRUIT.h5');
  expect(screen.queryByRole('button', { name: 'Calculate new only' })).not.toBeInTheDocument();
});

test('cleaning thresholds are collapsed and explicit edits reach the reviewed manifest job', async () => {
  postTreatment.mockResolvedValueOnce({ manifest }).mockResolvedValueOnce({ queue: { running: false, jobs: [] } });
  render(<VD2ManifestTreatment initialManifest={path} />);
  await screen.findByText('sample2');
  expect(screen.getByLabelText('SAM angle')).not.toBeVisible();
  expect(postTreatment).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText('Cleaning settings'));
  fireEvent.change(screen.getByLabelText('SAM angle'), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('SAM surface'), { target: { value: '3' } });
  fireEvent.change(screen.getByLabelText('Calculation mode'), { target: { value: 'averaged' } });
  fireEvent.click(screen.getByRole('button', { name: 'Recalculate all' }));
  await waitFor(() => expect(postTreatment).toHaveBeenCalledTimes(2));
  expect(postTreatment.mock.calls[1][2]).toEqual({ manifest_path: path, samples: ['sample1', 'sample2'], mode: 'all', clean: true, calc_mode: 'averaged', angle_threshold: 2, surface_threshold: 3 });
});

test('manifest dialog supports Escape without starting treatment', async () => {
  const onClose = jest.fn();
  postTreatment.mockResolvedValue({ manifest });
  render(<VD2ManifestTreatment dialog initialManifest={path} onClose={onClose} />);
  await screen.findByText('sample2');
  const dialog = screen.getByRole('dialog');
  expect(dialog).toHaveFocus();
  fireEvent.keyDown(dialog, { key: 'Escape' });
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(postTreatment).toHaveBeenCalledTimes(1);
});

test('quoted paste is normalized and loading notifies the parent which folder to open',async()=>{
  const loaded=jest.fn();postTreatment.mockResolvedValue({manifest:{...manifest,project_folder:'E:\\DATA_VD2\\2026\\day\\project'}});
  render(<VD2ManifestTreatment onLoaded={loaded}/>);
  fireEvent.click(screen.getByText('VD2 project manifest'));
  fireEvent.change(screen.getByRole('textbox',{name:'Manifest JSON path'}),{target:{value:` "${path}" `}});
  fireEvent.click(screen.getByRole('button',{name:'Load manifest'}));
  await waitFor(()=>expect(loaded).toHaveBeenCalledWith(expect.objectContaining({project_folder:'E:\\DATA_VD2\\2026\\day\\project'})));
  expect(postTreatment.mock.calls[0][2]).toEqual({manifest_path:path});
  expect(screen.getByRole('textbox',{name:'Manifest JSON path'})).toHaveValue(path);
});

test('reload reads persisted job status without automatically starting calculations',async()=>{
  fetchTreatmentQueue.mockResolvedValue({queue:{running:false,pending_count:0,jobs:[{job_id:'old',label:'water',status:'completed',phase:'saved'}]}});
  render(<VD2ManifestTreatment sessionId="own-window-manifest"/>);
  expect(await screen.findByLabelText('Manifest treatment jobs')).toHaveTextContent('water · completed');
  expect(fetchTreatmentQueue).toHaveBeenCalledWith('own-window-manifest');
  expect(postTreatment).not.toHaveBeenCalled();
});
