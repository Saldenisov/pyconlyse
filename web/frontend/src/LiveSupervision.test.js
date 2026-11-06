import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import LiveSupervision from './LiveSupervision';
import Elyse from './Elyse';

function fixture(session = 'receiver-one') {
  return { quality: 'FRESH', stale_after_seconds: 2, snapshot: { receiver_session: session, publications: {
    'VAM-A': { data: Array(64).fill(0.0052), stale: false, age_seconds: 0.1,
      error: { status: false, code: 0 }, lv_type: { type: 'LvVariant', contained_type: {
        type: 'Cluster', name: 'VAM-A', fields: Array(64).fill({ type: 'DBL' }),
      } } },
  } } };
}

test.each(['vide', 'synchro', 'fluides', 'modulateur', 'machine', 'radioprotection', 'ht', 'hf',
  'alimentations', 'voie-directe', 'voie-deviee', 'synoptique', 'newfocus', 'camera'])(
  'operator page %s has no provenance, source panels or embedded intent console', async (tab) => {
    const client = { telemetry: jest.fn().mockResolvedValue(fixture()), business: jest.fn(),
      stageIntent: jest.fn(), submitIntent: jest.fn(), replay: jest.fn() };
    const view = render(<LiveSupervision tab={tab} client={client} />);
    await waitFor(() => expect(client.telemetry).toHaveBeenCalledTimes(1));
    expect(screen.queryByText(/Sources des|Sources et|Provenance et limites|Commandes ACQ/)).not.toBeInTheDocument();
    expect(client.business).not.toHaveBeenCalled();
    expect(client.stageIntent).not.toHaveBeenCalled();
    expect(client.submitIntent).not.toHaveBeenCalled();
    expect(client.replay).not.toHaveBeenCalled();
    view.unmount();
  },
);

test('combined machine controls share one read-only poller and no command client', async () => {
  const client = { telemetry: jest.fn().mockResolvedValue(fixture()), replay: jest.fn(), stageIntent: jest.fn(), submitIntent: jest.fn() };
  const view = render(<LiveSupervision tab="machine" client={client} />);
  await waitFor(() => expect(client.telemetry).toHaveBeenCalledTimes(1));
  for (const name of ['HT', 'HF', 'Alimentations', 'Radioprotection']) {
    expect(screen.getByRole('region', { name: `${name} · lecture seule` })).toBeInTheDocument();
  }
  expect(client.replay).not.toHaveBeenCalled();
  expect(client.stageIntent).not.toHaveBeenCalled();
  expect(client.submitIntent).not.toHaveBeenCalled();
  view.unmount();
});

test('shows live pressure in Vide without a camera placeholder or any actuation buttons', async () => {
  const client = { telemetry: jest.fn().mockResolvedValue(fixture()), replay: jest.fn() };
  render(<LiveSupervision tab="vide" client={client} />);
  expect(await screen.findByText('-1,0')).toBeInTheDocument();
  expect(screen.getByLabelText('Sas Guide HF')).toHaveTextContent('-1,0 × 10−8');
  expect(screen.queryByText(/sans moyenne native/)).not.toBeInTheDocument();
  expect(screen.queryByText(/NI1409/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(client.replay).not.toHaveBeenCalled();
});

test('keeps healthy transport details collapsed instead of filling the operating view with notices', async () => {
  const client = { telemetry: jest.fn().mockResolvedValue(fixture()) };
  render(<LiveSupervision tab="modulateur" client={client} />);
  await waitFor(() => expect(client.telemetry).toHaveBeenCalledTimes(1));
  expect(screen.queryByText('Provenance et limites')).not.toBeInTheDocument();
  expect(screen.queryByText(/Sources des/)).not.toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.queryByText('Récent', { exact: true })).not.toBeInTheDocument();
});

test('stales values during a hung request', async () => {
  jest.useFakeTimers();
  const client = { telemetry: jest.fn().mockResolvedValueOnce(fixture()).mockImplementation(() => new Promise(() => {})) };
  try {
    const view = render(<LiveSupervision tab="vide" client={client} />);
    await screen.findByText('-1,0');
    expect(screen.getByLabelText('Sas Guide HF')).toHaveTextContent('-1,0 × 10−8');
    await act(async () => { jest.advanceTimersByTime(2250); });
    expect(screen.getByRole('alert')).toHaveTextContent('Télémétrie périmée');
    expect(screen.getByLabelText('Sas Guide HF')).toHaveTextContent('—');
    expect(client.telemetry).toHaveBeenCalledTimes(2);
    view.unmount();
  } finally { jest.useRealTimers(); }
});

test('hides last values immediately when the next HTTP read fails', async () => {
  jest.useFakeTimers();
  const client = { telemetry: jest.fn().mockResolvedValueOnce(fixture()).mockRejectedValue(new Error('HTTP failed')) };
  try {
    const view = render(<LiveSupervision tab="vide" client={client} />);
    await screen.findByText('-1,0');
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(screen.getByRole('alert')).toHaveTextContent('Télémétrie indisponible');
    expect(screen.queryByText(/HTTP failed/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Sas Guide HF')).toHaveTextContent('—');
    view.unmount();
  } finally { jest.useRealTimers(); }
});

test('switches pages using one latest-only poller, never a replay or hardware request', async () => {
  const client = { telemetry: jest.fn().mockResolvedValue(fixture()), snapshot: jest.fn().mockResolvedValue({
    dps_fields: [], pages: {}, display_fields: {},
  }), replay: jest.fn(), stageIntent: jest.fn(), submitIntent: jest.fn() };
  render(<Elyse client={client} />);
  fireEvent.click(screen.getByRole('tab', { name: 'Vide', exact: true }));
  await within(screen.getByRole('tabpanel', { name: 'Vide' })).findByText('-1,0');
  fireEvent.click(screen.getByRole('tab', { name: 'Modulateur', exact: true }));
  expect(screen.getByRole('group', { name: 'Étapes' })).toBeInTheDocument();
  expect(client.telemetry).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('complementary', { name: 'Réglages rapides ELYSE' })).not.toBeInTheDocument();
  expect(client.replay).not.toHaveBeenCalled();
  expect(client.stageIntent).not.toHaveBeenCalled();
  expect(client.submitIntent).not.toHaveBeenCalled();
});

test('Fluides receives two real temperature samples and retains its RAM curve across display tabs', async () => {
  jest.useFakeTimers();
  const sample = (sequence) => {
    const payload = fixture();
    const data = Array(64).fill(0); data[0] = 20.5 + sequence / 10; data[8] = 20.9;
    payload.snapshot.publications.C1NI6071E = { data, sequence,
      received_utc_on_everest: new Date(Date.parse('2026-10-16T14:00:00Z') + sequence * 1000).toISOString(),
      stale: false, age_seconds: 0.1, error: { status: false, code: 0 },
      lv_type: { type: 'Cluster', name: 'C1NI6071E', fields: Array(64).fill({ type: 'DBL' }) } };
    return payload;
  };
  const client = { telemetry: jest.fn().mockResolvedValueOnce(sample(1)).mockResolvedValue(sample(2)),
    submitIntent: jest.fn(), stageIntent: jest.fn() };
  try {
    const view = render(<LiveSupervision tab="vide" client={client} />);
    await screen.findByText('-1,0');
    view.rerender(<LiveSupervision tab="fluides" client={client} />);
    expect(screen.getByRole('img', { name: /CANON et SECTION · 1 points/ })).toBeInTheDocument();
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(screen.getByRole('img', { name: /CANON et SECTION · 2 points/ })).toBeInTheDocument();
    expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('20,7');
    view.rerender(<LiveSupervision tab="modulateur" client={client} />);
    view.rerender(<LiveSupervision tab="fluides" client={client} />);
    expect(screen.getByRole('img', { name: /CANON et SECTION · 2 points/ })).toBeInTheDocument();
    expect(client.telemetry).toHaveBeenCalledTimes(2);
    expect(client.stageIntent).not.toHaveBeenCalled();
    expect(client.submitIntent).not.toHaveBeenCalled();
    view.unmount();
  } finally { jest.useRealTimers(); }
});

test.each([['radioprotection', 'Radioprotection'], ['ht', 'HT'], ['hf', 'HF'], ['alimentations', 'Alimentations']])(
  'uses the native-style %s panel without extra generic values, graphs or command authority', async (tab, name) => {
    const client = { telemetry: jest.fn().mockResolvedValue(fixture()), replay: jest.fn(),
      stageIntent: jest.fn(), submitIntent: jest.fn() };
    const view = render(<LiveSupervision tab={tab} client={client} />);
    await waitFor(() => expect(client.telemetry).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('region', { name: `${name} · lecture seule` })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Entrées logiques|Vide · dernières valeurs|Étapes logicielles/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    screen.queryAllByRole('button').forEach((button) => expect(button).toBeDisabled());
    expect(client.telemetry).toHaveBeenCalledTimes(1);
    expect(client.replay).not.toHaveBeenCalled();
    expect(client.stageIntent).not.toHaveBeenCalled();
    expect(client.submitIntent).not.toHaveBeenCalled();
    view.unmount();
  },
);
