import React, { useState } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import TreatmentPanel, { validateTreatmentOperation, validateTreatmentRecipe } from './TreatmentPanel';
import { pumpProbeRequest } from './shared';
import { fetchWithCsrfToken } from '../api/csrfRequest';

jest.mock('./shared', () => ({ API_BASE: '/api/pump-probe-v0', pumpProbeRequest: jest.fn() }));
jest.mock('../api/csrfRequest', () => ({ fetchWithCsrfToken: jest.fn() }));

const source = { path: '/data/sample.zip', file_name: 'sample.zip', source_sha256: 'a'.repeat(64),
  heatmap: [[1]], wavelengths: [500], delays: [0], operations: [], capabilities: ['scale', 'raw_od', 'raw_background'] };

function Harness({ onPreview, onApply }) {
  const [applied, setApplied] = useState(source);
  return <TreatmentPanel source={source} applied={applied} onPreview={onPreview}
    onApply={(value) => { setApplied(value); onApply(value); }} onClose={jest.fn()} />;
}

beforeEach(() => { pumpProbeRequest.mockReset(); fetchWithCsrfToken.mockReset(); });

test('preview, cancel and apply have separate boundaries; scaling chains applied recipe', async () => {
  const onPreview = jest.fn();
  const onApply = jest.fn();
  const result = { ...source, heatmap: [[2]], operations: [{ kind: 'scale', factor: 2 }] };
  pumpProbeRequest.mockResolvedValue(result);
  render(<Harness onPreview={onPreview} onApply={onApply} />);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  expect(onApply).not.toHaveBeenCalled();
  expect(onPreview).toHaveBeenLastCalledWith(result);
  fireEvent.click(screen.getByRole('button', { name: 'Cancel preview' }));
  expect(onPreview).toHaveBeenLastCalledWith(null);
  expect(onApply).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
  expect(onApply).toHaveBeenLastCalledWith(result);
  expect(screen.getByText('1 applied corrections (in memory).')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  const request = JSON.parse(pumpProbeRequest.mock.calls[2][1].body);
  expect(request.operations).toEqual([{ kind: 'scale', factor: 2 }, { kind: 'scale', factor: 2 }]);
  expect(request.source_sha256).toBe(source.source_sha256);
});

test('parameter change invalidates preview and reset restores source', async () => {
  const onPreview = jest.fn();
  const onApply = jest.fn();
  pumpProbeRequest.mockResolvedValue({ ...source, heatmap: [[2]], operations: [{ kind: 'scale', factor: 2 }] });
  render(<Harness onPreview={onPreview} onApply={onApply} />);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  fireEvent.change(screen.getByLabelText('Scale factor'), { target: { value: '3' } });
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  expect(onPreview).toHaveBeenLastCalledWith(null);
  fireEvent.click(screen.getByRole('button', { name: 'Reset to source' }));
  expect(onApply).toHaveBeenLastCalledWith(source);
});

test('RAW background starts from original shots with explicit zero policy', async () => {
  pumpProbeRequest.mockResolvedValue({ ...source, heatmap: [[.1]] });
  render(<TreatmentPanel source={source} applied={{ ...source, operations: [{ kind: 'scale', factor: 3 }] }}
    onPreview={jest.fn()} onApply={jest.fn()} onClose={jest.fn()} />);
  fireEvent.change(screen.getByLabelText('Operation'), { target: { value: 'raw_background' } });
  fireEvent.change(screen.getByLabelText('Detector I, counts'), { target: { value: '7' } });
  fireEvent.change(screen.getByLabelText('Detector II, counts'), { target: { value: '-3' } });
  fireEvent.change(screen.getByLabelText('Stored zero slots'), { target: { value: 'drop_whole_zero' } });
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByText('Preview shown; changes pending.');
  expect(JSON.parse(pumpProbeRequest.mock.calls[0][1].body).operations).toEqual([
    { kind: 'raw_background', counts: [7, -3], zero_slot_policy: 'drop_whole_zero' },
  ]);
});

test('failed source fingerprint does not apply or leave an active preview', async () => {
  const onApply = jest.fn();
  pumpProbeRequest.mockRejectedValue(new Error('Source file changed; reload before applying corrections'));
  render(<Harness onPreview={jest.fn()} onApply={onApply} />);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  expect(onApply).not.toHaveBeenCalled();
});

test('closing/unmounting aborts request and ignores late results', async () => {
  let finish;
  pumpProbeRequest.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  const onPreview = jest.fn();
  const rendered = render(<Harness onPreview={onPreview} onApply={jest.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
  const signal = pumpProbeRequest.mock.calls[0][1].signal;
  rendered.unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => finish({ ...source, heatmap: [[99]] }));
  expect(onPreview).toHaveBeenCalledTimes(1); // clearing old preview only
});

test('unknown RAW semantics do not offer RAW correction', () => {
  render(<TreatmentPanel source={{ ...source, capabilities: ['scale'] }} applied={source}
    onPreview={jest.fn()} onApply={jest.fn()} onClose={jest.fn()} />);
  expect(screen.queryByRole('option', { name: 'Recalculate original RAW' })).not.toBeInTheDocument();
});

test('DAT download uses applied recipe and source fingerprint, preserving CSRF transport', async () => {
  const applied = { ...source, operations: [{ kind: 'scale', factor: 3 }] };
  const blob = new Blob(['0\t1\n500\t3\n']);
  fetchWithCsrfToken.mockResolvedValue({ ok: true, blob: async () => blob });
  const originalCreate = URL.createObjectURL;
  const originalRevoke = URL.revokeObjectURL;
  URL.createObjectURL = jest.fn(() => 'blob:test');
  URL.revokeObjectURL = jest.fn();
  const click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  try {
    render(<TreatmentPanel source={source} applied={applied}
      onPreview={jest.fn()} onApply={jest.fn()} onClose={jest.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Download DAT' }));
    await act(async () => {});
    expect(fetchWithCsrfToken.mock.calls[0][0]).toBe('/api/pump-probe-v0/data/treat');
    expect(JSON.parse(fetchWithCsrfToken.mock.calls[0][1].body)).toEqual({
      path: source.path, source_sha256: source.source_sha256,
      operations: applied.operations, format: 'dat',
    });
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(click).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Download DAT' })).toBeEnabled();
  } finally {
    click.mockRestore();
    URL.createObjectURL = originalCreate;
    // Pending URL cleanup must retain a callable revoke function.
    URL.revokeObjectURL = originalRevoke || jest.fn();
  }
});

test('DAT download failure is visible and leaves applied dataset unchanged', async () => {
  const onApply = jest.fn();
  fetchWithCsrfToken.mockResolvedValue({ ok: false, json: async () => ({ error: 'Source file changed; reload' }) });
  render(<Harness onPreview={jest.fn()} onApply={onApply} />);
  fireEvent.click(screen.getByRole('button', { name: 'Download DAT' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Source file changed; reload');
  expect(onApply).not.toHaveBeenCalled();
});
