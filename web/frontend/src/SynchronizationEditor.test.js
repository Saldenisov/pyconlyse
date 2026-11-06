import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import SynchronizationEditor from './SynchronizationEditor';
import { ACQ_TIMING } from './elyseLiveProjection';

function telemetry() {
  return { elapsed: 0, failure: '', payload: { stale_after_seconds: 2, snapshot: { publications: {
    C1011NI6602: { data: Array.from({ length: 33 }, (_, i) => i + 0.5), stale: false, age_seconds: 0,
      error: { status: false, code: 0 }, lv_type: { type: 'Cluster', name: 'C10-11 NI6602', fields: Array(33).fill({ type: 'DBL' }) } },
  } } } };
}

test('shows actual readback separately from a saved draft, never enables hardware apply', async () => {
  const client = { synchronizationDraft: jest.fn().mockResolvedValue({ revision: 3, hardware_applied: false, values: Array(33).fill(99) }) };
  render(<SynchronizationEditor telemetry={telemetry()} client={client} />);
  expect(await screen.findByText(/Brouillon restauré/)).toBeInTheDocument();
  expect(screen.getByLabelText(`${ACQ_TIMING[0].label} · lecture`)).toHaveTextContent('0,50');
  expect(screen.getByLabelText(`${ACQ_TIMING[0].label} · brouillon`)).toHaveValue(99);
  expect(screen.getByRole('button', { name: 'Appliquer à ACQ' })).toBeDisabled();
});

test('copy, edit and save persists explicit values with the loaded revision only', async () => {
  const client = { synchronizationDraft: jest.fn().mockResolvedValue({ revision: 4, hardware_applied: false, values: null }),
    saveSynchronizationDraft: jest.fn().mockResolvedValue({ revision: 5, hardware_applied: false }) };
  render(<SynchronizationEditor telemetry={telemetry()} client={client} />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enregistrer brouillon Synchro' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Copier lectures ACQ' }));
  fireEvent.change(screen.getByLabelText(`${ACQ_TIMING[0].label} · brouillon`), { target: { value: '2.5' } });
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer brouillon Synchro' }));
  await waitFor(() => expect(client.saveSynchronizationDraft).toHaveBeenCalledTimes(1));
  expect(client.saveSynchronizationDraft.mock.calls[0][0]).toEqual([2.5, ...Array.from({ length: 32 }, (_, i) => i + 1.5)]);
  expect(client.saveSynchronizationDraft.mock.calls[0][1]).toBe(4);
  expect(await screen.findByText(/aucune consigne appliquée/)).toBeInTheDocument();
});

test('unknown or stale readback cannot fill a draft with fabricated zeros', () => {
  const value = telemetry(); value.elapsed = 3;
  const client = { saveSynchronizationDraft: jest.fn() };
  render(<SynchronizationEditor telemetry={value} client={client} />);
  fireEvent.click(screen.getByRole('button', { name: 'Copier lectures ACQ' }));
  expect(screen.getByText(/aucune valeur inconnue remplacée par zéro/)).toBeInTheDocument();
  expect(screen.getByLabelText(`${ACQ_TIMING[0].label} · brouillon`)).toHaveValue(null);
  expect(client.saveSynchronizationDraft).not.toHaveBeenCalled();
});

test('telemetry refresh never overwrites an operator draft', () => {
  const value = telemetry(); const client = {};
  const view = render(<SynchronizationEditor telemetry={value} client={client} />);
  fireEvent.change(screen.getByLabelText(`${ACQ_TIMING[0].label} · brouillon`), { target: { value: '8.7' } });
  const changed = telemetry(); changed.payload.snapshot.publications.C1011NI6602.data[0] = 123;
  view.rerender(<SynchronizationEditor telemetry={changed} client={client} />);
  expect(screen.getByLabelText(`${ACQ_TIMING[0].label} · lecture`)).toHaveTextContent('123,00');
  expect(screen.getByLabelText(`${ACQ_TIMING[0].label} · brouillon`)).toHaveValue(8.7);
});
