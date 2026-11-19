import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ExperimentPreparation from './ExperimentPreparation';

const originalFetch = global.fetch;
const phase = 'manip/CR/ANDOR_KYMERA1: Attempting device recovery command turn_on; server retained';
const running = {
  job_id: 'prepare-1', status: 'running', operation: 'prepare', phase,
  created_at: 850, updated_at: 990, server_time: 1000,
  events: [
    { job_id: 'old-job', kind: 'progress', message: phase, timestamp: 999 },
    { job_id: 'prepare-1', kind: 'progress', message: phase, timestamp: 900 },
  ],
};
const response = job => ({ ok: true, json: async () => ({ success: true, job }) });
const show = () => render(<MemoryRouter initialEntries={['/?experiment=VD2']}><ExperimentPreparation /></MemoryRouter>);

beforeEach(() => { jest.useFakeTimers(); global.fetch = jest.fn(); });
afterEach(() => { global.fetch = originalFetch; jest.useRealTimers(); });

test('SDK wait shows readable phase and keeps ticking through identical snapshots using server time', async () => {
  global.fetch.mockResolvedValue(response(running));
  show();
  await act(async () => {});
  expect(screen.getByRole('status')).toHaveTextContent('Initializing Kymera — please wait');
  expect(screen.queryByText(/Attempting device recovery command/)).not.toBeInTheDocument();
  expect(screen.getByRole('timer')).toHaveTextContent('Stage 01:40 · Total 02:30');
  await act(async () => { jest.advanceTimersByTime(3000); });
  expect(screen.getByRole('timer')).toHaveTextContent('Stage 01:43 · Total 02:33');
  expect(global.fetch.mock.calls.every(([url, options]) => url.endsWith('/lifecycle') && !options.method)).toBe(true);
});

test('new phase resets stage timer while total survives and completed operation removes timer', async () => {
  global.fetch.mockResolvedValueOnce(response(running))
    .mockResolvedValueOnce(response({ ...running, phase: 'Switching the streak camera to Focus',
      updated_at: 1001, server_time: 1001, events: [] }))
    .mockResolvedValue(response({ ...running, status: 'completed', phase: 'Operation completed', updated_at: 1002 }));
  show();
  await act(async () => {});
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('timer')).toHaveTextContent('Stage 00:00 · Total 02:31');
  await act(async () => { jest.advanceTimersByTime(1000); });
  expect(screen.getByRole('status')).toHaveTextContent('Operation completed');
  expect(screen.queryByRole('timer')).not.toBeInTheDocument();
});

test('actual recovery failure is preserved instead of replaced by a waiting message', async () => {
  const error = `${phase}: SDK initialization failed`;
  global.fetch.mockResolvedValue(response({ ...running, status: 'failed', error }));
  show();
  await act(async () => {});
  expect(screen.getByRole('alert')).toHaveTextContent(error);
  expect(screen.queryByRole('timer')).not.toBeInTheDocument();
});
