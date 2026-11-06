import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import AcqTelemetry, { telemetryRows } from './AcqTelemetry';

function payload(value = 1.25) {
  return { schema_version: 1, execution_allowed: false, server_state: 'ON', quality: 'FRESH',
    expected_banks: ['C1NI6071E', 'DPS'], stale_after_seconds: 2, error_banks: [],
    snapshot: { receiver_session: 'session-a', received_this_process: 12, duplicate_receipts: 0,
      publications: { C1NI6071E: { data: [value, false], age_seconds: 0.1, stale: false, sequence: 9,
        error: { status: false, code: 0, source: '' }, received_utc_on_everest: '2026-10-16T11:55:00Z',
        lv_type: { type: 'LvVariant', contained_type: { type: 'Cluster', fields: [
          { type: 'DBL', name: 'Mes température Canon' }, { type: 'Boolean', name: 'Interrupteur' }] } } } } } };
}

beforeEach(() => { jest.useFakeTimers(); });
afterEach(() => { jest.useRealTimers(); });
async function mount(client) {
  const view = render(<AcqTelemetry client={client} />);
  await screen.findByText('Flux récent');
  return view;
}

test('shows typed names and neutral booleans, no hardware controls', async () => {
  const client = { telemetry: jest.fn().mockResolvedValue(payload()) };
  const view = await mount(client);
  expect(screen.getByText('Mes température Canon')).toBeInTheDocument();
  expect(screen.getByText('1.25')).toBeInTheDocument();
  expect(screen.getByText('FALSE')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Start|Stop|Marche|Écrire/ })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Canon' } });
  expect(screen.queryByText('FALSE')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /DPS/ }));
  expect(screen.getByText('Aucune valeur reçue pour cette banque.')).toBeInTheDocument();
  view.unmount();
});

test('polls updates and marks changed value, then aborts on unmount', async () => {
  const client = { telemetry: jest.fn().mockResolvedValueOnce(payload()).mockResolvedValue(payload(3.5)) };
  const view = await mount(client);
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('row', { name: /Mes température Canon/ })).toHaveClass('acq-telemetry__changed');
  expect(client.telemetry).toHaveBeenCalledTimes(2);
  const signal = client.telemetry.mock.calls[1][0];
  view.unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => { jest.advanceTimersByTime(5000); });
  expect(client.telemetry).toHaveBeenCalledTimes(2);
});

test('values become stale while an HTTP read hangs, even though receiver was ON', async () => {
  const client = { telemetry: jest.fn().mockResolvedValueOnce(payload()).mockImplementation(() => new Promise(() => {})) };
  const view = await mount(client);
  await act(async () => { jest.advanceTimersByTime(3000); });
  expect(screen.getByText('Données périmées')).toBeInTheDocument();
  expect(screen.getByText('DERNIÈRES VALEURS · PÉRIMÉES')).toBeInTheDocument();
  expect(screen.getByText('ON')).toBeInTheDocument();
  view.unmount();
});

test('connection failure retains only labelled last values and recovers', async () => {
  const client = { telemetry: jest.fn().mockResolvedValueOnce(payload()).mockRejectedValueOnce(new Error('offline')).mockResolvedValue(payload(8)) };
  const view = await mount(client);
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('alert')).toHaveTextContent('Dernier instantané conservé');
  expect(screen.getByText('1.25')).toBeInTheDocument();
  expect(screen.queryByText('Flux récent')).not.toBeInTheDocument();
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByText('Flux récent')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  view.unmount();
});

test('receiver restart clears old values instead of mixing sessions', async () => {
  const reset = payload();
  reset.quality = 'WAITING'; reset.snapshot.receiver_session = 'session-b';
  reset.snapshot.publications = {}; reset.snapshot.received_this_process = 0;
  const client = { telemetry: jest.fn().mockResolvedValueOnce(payload()).mockResolvedValue(reset) };
  const view = await mount(client);
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.queryByText('1.25')).not.toBeInTheDocument();
  expect(screen.getByText(/Session du récepteur modifiée/)).toBeInTheDocument();
  expect(screen.getByText('En attente de données')).toBeInTheDocument();
  view.unmount();
});

test('preserves empty, nonfinite and exact I64 values', () => {
  const type = { type: 'Cluster', fields: [ { name: 'Vide', type: 'Array' },
    { name: 'Non fini', type: 'DBL' }, { name: 'Compteur', type: 'I64' } ] };
  expect(telemetryRows([[], { nonfinite: 'NaN' }, { integer_decimal: '9223372036854775807' }], type)
    .map((row) => row.value)).toEqual(['[]', 'NaN', '9223372036854775807']);
});

test('Python uses the same bank navigation with honest unavailable states', () => {
  const data = payload();
  data.quality = 'INCOMPLETE'; data.snapshot.source = 'python_daqmx_acquisition';
  data.expected_banks = ['C1NI6071E', 'EPS'];
  data.snapshot.publications.EPS = { data: null, age_seconds: .1, stale: false,
    error: { status: true, code: -80001, source: 'PYTHON_BANK_NOT_YET_MIGRATED' },
    lv_type: { type: 'LvVariant', contained_type: { type: 'Cluster', name: 'EPS', fields: [] } } };
  render(<AcqTelemetry telemetry={{ payload: data, failure: '', elapsed: 0 }} />);
  expect(screen.getByText('Banques manquantes ou indisponibles')).toBeInTheDocument();
  expect(screen.getByText(/Acquisition Python.*Everest/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /EPS indisponible/ }));
  expect(screen.getByRole('alert')).toHaveTextContent('Acquisition Python -80001');
  expect(screen.queryByText('FALSE')).not.toBeInTheDocument();
});

test('shows the physical C3 card, different VI labels and pin with the indexed live value', () => {
  const data = payload();
  data.expected_banks = ['C3_IN_DIO96'];
  data.snapshot.publications.C3_IN_DIO96 = {
    data: Array.from({ length: 56 }, (_, index) => index === 6),
    lv_type: { type: 'Cluster', fields: Array.from({ length: 56 }, () => ({ type: 'Boolean' })) },
    age_seconds: .1,
  };
  render(<AcqTelemetry telemetry={{ payload: data, failure: '', elapsed: 0 }} />);
  fireEvent.click(screen.getByRole('button', { name: /C3_IN_DIO96/ }));
  expect(screen.getByRole('heading', { name: 'C3_IN_DIO96 (PCI-DIO-96)' })).toBeInTheDocument();
  expect(screen.getByRole('columnheader', { name: 'Champ LabVIEW SuperVision' })).toBeInTheDocument();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'APA6' } });
  const row = screen.getByRole('row', { name: /Reffroidissement Section marche/ });
  expect(row).toHaveTextContent('Fluides[17] · Section Secteur 220 V');
  expect(within(row).getByText('35 · APA6')).toHaveAttribute('title', '/3/port0/line6');
  expect(row).toHaveTextContent('TRUE');
  expect(screen.queryByText('47 · APA0')).not.toBeInTheDocument();
});

test('keeps the pinout available without a received snapshot and leaves values empty', () => {
  render(<AcqTelemetry telemetry={{ payload: null, failure: 'Lecture indisponible', elapsed: 0 }} />);
  fireEvent.click(screen.getByRole('button', { name: /C3_IN_DIO96/ }));
  const row = screen.getByRole('row', { name: /Reffroidissement Canon marche/ });
  expect(within(row).getByText('47 · APA0')).toBeInTheDocument();
  expect(within(row).getByRole('status')).toHaveTextContent('—');
  expect(screen.getByText('Aucune valeur reçue pour cette banque.')).toBeInTheDocument();
});
