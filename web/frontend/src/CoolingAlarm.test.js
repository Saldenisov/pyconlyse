import React from 'react';
import { act, render, screen } from '@testing-library/react';
import CoolingAlarm, { CoolingAlarmDisplay } from './CoolingAlarm';

function fixture() {
  return { schema_version: 1, active: true, quality: 'FRESH', remaining_seconds: 120,
    automatic_stop_available: true, stop_state: 'NONE', journal_durable: true, journal: [],
    circuits: [{ circuit: 'SECTION', started_utc: '2026-10-21T10:40:46Z', deadline_utc: '2026-10-21T10:42:46Z' }] };
}

test('explicit circuit/time/120-second warning and no hardware controls', () => {
  render(<CoolingAlarmDisplay safety={fixture()} telemetry={{ elapsed: 1 }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('PERTE DE CIRCULATION — SECTION');
  expect(screen.getByRole('alert')).toHaveTextContent('119 s');
  expect(screen.getByRole('alert')).toHaveTextContent('12:40:46');
  expect(screen.getByRole('alert')).toHaveTextContent('arrêt forcé');
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

test('read-only LabVIEW receiver never promises physical shutdown', () => {
  const safety = { ...fixture(), automatic_stop_available: false };
  render(<CoolingAlarmDisplay safety={safety} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Arrêt automatique NON DISPONIBLE');
  expect(screen.getByRole('alert')).not.toHaveTextContent('le serveur demandera');
});

test('stale telemetry leaves alarm visible, no recovery or successful-stop fabrication', () => {
  render(<CoolingAlarmDisplay safety={fixture()} sourceFailure="offline" telemetry={{ elapsed: 122 }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('0 s');
  expect(screen.getByRole('alert')).toHaveTextContent('Le délai serveur n’est pas annulé');
  expect(screen.getByRole('alert')).not.toHaveTextContent('COMPLETED');
});

test('historical journal alone does not create an alarm banner after recovery', () => {
  const safety = { ...fixture(), active: false, circuits: [], remaining_seconds: null,
    journal: [{ kind: 'CIRCULATION_RESTORED', circuit: 'SECTION', observed_utc: '2026-10-21T10:41:00Z' }] };
  const view = render(<CoolingAlarmDisplay safety={safety} />);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(view.container).toBeEmptyDOMElement();
});

test('current alarm details contain no duplicated historical journal', () => {
  const journal = [
    { kind: 'OLDER', observed_utc: '2026-10-22T18:36:56Z' },
    { kind: 'NEWEST', observed_utc: '2026-10-26T12:22:25Z' },
  ];
  render(<CoolingAlarmDisplay safety={{ ...fixture(), journal }} />);
  expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
  expect(screen.queryByText('Journal des alarmes')).not.toBeInTheDocument();
  expect(screen.queryByText(/NEWEST/)).not.toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('SECTION');
  expect(journal[0].kind).toBe('OLDER');
});

test('stop failure and storage failure are explicit', () => {
  render(<CoolingAlarmDisplay safety={{ ...fixture(), stop_state: 'FAILED', stop_error: 'HT feedback', journal_error: 'disk full' }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('FAILED — HT feedback');
  expect(screen.getByRole('alert')).toHaveTextContent('ERREUR JOURNAL : disk full');
});

test('unknown circulation while machine active is a visible supervision fault, not healthy or invented loss', () => {
  render(<CoolingAlarmDisplay safety={{ ...fixture(), active: false, circuits: [], quality: 'UNKNOWN',
    machine_active: true, remaining_seconds: null }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('circulation non confirmée');
  expect(screen.getByRole('alert')).not.toHaveTextContent('PERTE DE CIRCULATION');
  expect(screen.getByRole('alert')).not.toHaveTextContent('COUNTDOWN');
});

test('server failure after a previously healthy response is explicit, not hidden by cached health', async () => {
  jest.useFakeTimers();
  try {
    const healthy = { ...fixture(), active: false, circuits: [], remaining_seconds: null };
    const client = { coolingSafety: jest.fn().mockResolvedValueOnce({ cooling_safety: healthy })
      .mockRejectedValue(new Error('offline')) };
    const view = render(<CoolingAlarm client={client} />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { jest.advanceTimersByTime(1000); await Promise.resolve(); });
    expect(screen.getByRole('alert')).toHaveTextContent('Alarme refroidissement indisponible');
    expect(screen.getByRole('alert')).toHaveTextContent('offline');
    view.unmount();
  } finally { jest.useRealTimers(); }
});

test('cached incident survives failed polling and unmount cancels polling, not server countdown', async () => {
  jest.useFakeTimers();
  try {
    const client = { coolingSafety: jest.fn().mockResolvedValueOnce({ cooling_safety: fixture() })
      .mockRejectedValue(new Error('offline')) };
    const view = render(<CoolingAlarm client={client} />);
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByRole('alert')).toHaveTextContent('120 s');
    await act(async () => { jest.advanceTimersByTime(1000); await Promise.resolve(); });
    expect(screen.getByRole('alert')).toHaveTextContent('PERTE DE CIRCULATION — SECTION');
    expect(screen.getByRole('alert')).toHaveTextContent('Le délai serveur n’est pas annulé');
    const calls = client.coolingSafety.mock.calls.length;
    view.unmount();
    await act(async () => { jest.advanceTimersByTime(3000); });
    expect(client.coolingSafety).toHaveBeenCalledTimes(calls);
  } finally { jest.useRealTimers(); }
});

test('slow healthy replies do not add a full polling pause or create a spurious cooling alarm', async () => {
  jest.useFakeTimers();
  try {
    const healthy = { ...fixture(), active: false, circuits: [], remaining_seconds: null };
    let active = 0, maximum = 0;
    const client = { coolingSafety: jest.fn(() => {
      active += 1; maximum = Math.max(maximum, active);
      return new Promise(resolve => setTimeout(() => {
        active -= 1; resolve({ cooling_safety: healthy });
      }, 850));
    }) };
    const view = render(<CoolingAlarm client={client} />);
    for (let i = 0; i < 200; i += 1) {
      await act(async () => { jest.advanceTimersByTime(25); });
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    }
    expect(maximum).toBe(1);
    expect(client.coolingSafety.mock.calls.length).toBeGreaterThanOrEqual(5);
    view.unmount();
  } finally { jest.useRealTimers(); }
});

test('a hung cooling read still expires and leaves an active server incident visible', async () => {
  jest.useFakeTimers();
  try {
    const client = { coolingSafety: jest.fn().mockResolvedValueOnce({ cooling_safety: fixture() })
      .mockImplementation(() => new Promise(() => {})) };
    const view = render(<CoolingAlarm client={client} />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { jest.advanceTimersByTime(2250); });
    expect(screen.getByRole('alert')).toHaveTextContent('PERTE DE CIRCULATION');
    expect(screen.getByRole('alert')).toHaveTextContent('Le délai serveur n’est pas annulé');
    expect(client.coolingSafety).toHaveBeenCalledTimes(2);
    view.unmount();
  } finally { jest.useRealTimers(); }
});

test('a startup red indication has no invented120-second deadline', () => {
  render(<CoolingAlarmDisplay safety={{ ...fixture(), countdown_required: false,
    confirmation_required: false, confirmation_candidates: [], remaining_seconds: null }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('SIGNAL REFROIDISSEMENT ROUGE');
  expect(screen.getByRole('alert')).not.toHaveTextContent('COUNTDOWN');
  expect(screen.getByRole('alert')).not.toHaveTextContent('échéance');
});

test('operator confirmation retains red warning while canceling only additional deadline for that episode', () => {
  const safety = fixture(); safety.circuits[0] = { ...safety.circuits[0], incident_id: '1'.repeat(32),
    water_confirmation_received: true, confirmed_by: 'operator', confirmed_utc: '2026-10-21T10:41:00Z' };
  render(<CoolingAlarmDisplay safety={{ ...safety, countdown_required: false, confirmation_required: false,
    confirmation_candidates: [], remaining_seconds: null }} />);
  const warning = screen.getByRole('alert');
  expect(warning).toHaveTextContent('SIGNAL REFROIDISSEMENT ROUGE');
  expect(warning).toHaveTextContent('Circulation physique confirmée par operator');
  expect(warning).toHaveTextContent('Arrêt supplémentaire de 120 s annulé pour cet incident uniquement');
  expect(warning).toHaveTextContent('garde VI restent inchangées');
  expect(warning).not.toHaveTextContent('COUNTDOWN'); expect(warning).not.toHaveTextContent('échéance');
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

test('a confirmed episode cannot hide another circuit’s pending120-second deadline', () => {
  const safety = fixture();
  safety.circuits = [{ ...safety.circuits[0], incident_id: '1'.repeat(32), water_confirmation_received: true,
    confirmed_by: 'operator', confirmed_utc: '2026-10-21T10:41:00Z' },
  { circuit: 'CANON', incident_id: '2'.repeat(32), started_utc: '2026-10-21T10:41:00Z', deadline_utc: '2026-10-21T10:43:00Z' }];
  render(<CoolingAlarmDisplay safety={{ ...safety, countdown_required: true, confirmation_required: true,
    confirmation_candidates: [{ incident_id: '2'.repeat(32) }], remaining_seconds: 60 }} />);
  expect(screen.getByRole('alert')).toHaveTextContent('COUNTDOWN — 60 s');
  expect(screen.getByRole('alert')).toHaveTextContent('12:43:00');
  expect(screen.getByRole('alert')).not.toHaveTextContent('12:42:46');
});
