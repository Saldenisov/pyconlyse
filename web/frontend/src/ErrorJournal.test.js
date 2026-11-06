import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import ErrorJournal from './ErrorJournal';

const fixture = (extra = {}) => ({ schema_version: 1, storage: 'server_sqlite', execution_allowed: false,
  observed_utc: '2026-10-26T12:00:00Z', observer_running: true, journal_error: '', sources: [],
  events: [{ id: 2, observed_utc: '2026-10-26T11:22:25Z', recorded_utc: '2026-10-26T12:00:00Z',
    source: 'labview', kind: 'PRIOR_EXPERIMENT_INCIDENT_ARCHIVED', circuit: 'CANON', category: 'source_alarm',
    details: { causes: [{ bank: 'C3_IN_DIO96', index: 0, raw: true }] } }],
  days: [{ day: '2026-10-26', count: 1 }], next_cursor: null, note: 'Historique reçu uniquement.', ...extra });

test('shows full date, source and preserved raw indications without command controls', async () => {
  const client = { errorJournal: jest.fn().mockResolvedValue(fixture()) };
  render(<ErrorJournal client={client} />);
  expect(await screen.findByText('PRIOR_EXPERIMENT_INCIDENT_ARCHIVED')).toBeInTheDocument();
  expect(screen.getByText(/26\/10\/2026.*12:22:25/)).toBeInTheDocument();
  expect(screen.getByText(/"raw": true/)).toBeInTheDocument();
  expect(client.errorJournal).toHaveBeenCalledWith({ day: '', cursor: '' }, expect.any(AbortSignal));
  expect(screen.queryByRole('button', { name: /arrêt|acquitter|reset/i })).not.toBeInTheDocument();
});

test('day selection, older page and latest button perform read queries', async () => {
  const client = { errorJournal: jest.fn().mockResolvedValue(fixture({ next_cursor: '123:2' })) };
  render(<ErrorJournal client={client} />);
  await screen.findByText('PRIOR_EXPERIMENT_INCIDENT_ARCHIVED');
  fireEvent.click(screen.getByRole('button', { name: '2026-10-26 · 1' }));
  await screen.findByText('PRIOR_EXPERIMENT_INCIDENT_ARCHIVED');
  expect(client.errorJournal.mock.calls.at(-1)[0]).toEqual({ day: '2026-10-26', cursor: '' });
  fireEvent.click(screen.getByRole('button', { name: 'Événements plus anciens' }));
  await screen.findByText('PRIOR_EXPERIMENT_INCIDENT_ARCHIVED');
  expect(client.errorJournal.mock.calls.at(-1)[0]).toEqual({ day: '2026-10-26', cursor: '123:2' });
  fireEvent.click(screen.getByRole('button', { name: 'Derniers événements' }));
  await screen.findByText('PRIOR_EXPERIMENT_INCIDENT_ARCHIVED');
  expect(client.errorJournal.mock.calls.at(-1)[0]).toEqual({ day: '', cursor: '' });
});

test('storage error and obsolete source remain explicit', async () => {
  const client = { errorJournal: jest.fn().mockResolvedValue(fixture({ journal_error: 'disk full',
    sources: [{ source: 'labview', quality: 'FRESH', last_observed_utc: '2026-01-01T00:00:00Z',
      journal_error: 'prior writer incomplete', journal_durable: false }] })) };
  render(<ErrorJournal client={client} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('disk full');
  expect(screen.getByText(/OBSERVATION PÉRIMÉE/)).toHaveTextContent('prior writer incomplete');
});

test('poll failure retains rows but labels them unrefreshed, unmount aborts', async () => {
  jest.useFakeTimers();
  try {
    const client = { errorJournal: jest.fn().mockResolvedValueOnce(fixture()).mockRejectedValue(new Error('offline')) };
    const view = render(<ErrorJournal client={client} />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => { jest.advanceTimersByTime(5000); await Promise.resolve(); });
    expect(screen.getByRole('alert')).toHaveTextContent('offline');
    expect(screen.getByRole('alert')).toHaveTextContent('ne sont pas actualisées');
    expect(screen.getByText('PRIOR_EXPERIMENT_INCIDENT_ARCHIVED')).toBeInTheDocument();
    view.unmount();
    expect(client.errorJournal.mock.calls.at(-1)[1].aborted).toBe(true);
    const calls = client.errorJournal.mock.calls.length;
    await act(async () => { jest.advanceTimersByTime(10000); });
    expect(client.errorJournal).toHaveBeenCalledTimes(calls);
  } finally { jest.useRealTimers(); }
});

test('old day response cannot replace a new filter and empty archive does not imply healthy equipment', async () => {
  let settle;
  const client = { errorJournal: jest.fn().mockImplementationOnce(() => new Promise((resolve) => { settle = resolve; }))
    .mockResolvedValue(fixture({ events: [] })) };
  render(<ErrorJournal client={client} />);
  fireEvent.change(screen.getByLabelText('Jour · Europe/Paris'), { target: { value: '2026-10-25' } });
  expect(await screen.findByText(/ne confirme pas l’absence de défaut/)).toBeInTheDocument();
  await act(async () => { settle(fixture()); });
  expect(screen.queryByText('PRIOR_EXPERIMENT_INCIDENT_ARCHIVED')).not.toBeInTheDocument();
});
