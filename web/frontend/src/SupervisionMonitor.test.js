import React from 'react';
import { render, screen, within } from '@testing-library/react';
import SupervisionMonitor from './SupervisionMonitor';

const telemetry = { payload: null, elapsed: 0, failure: 'offline' };

test('unbound image and profiles remain unavailable rather than substitute another camera', () => {
  render(<SupervisionMonitor telemetry={telemetry} />);
  expect(screen.getByRole('status', { name: 'État vidéo SuperVision' })).toHaveTextContent('En attente d’image');
  expect(screen.getByText('X · aucune mesure')).toBeInTheDocument();
  expect(screen.getByText(/Historique du vide indisponible/)).toBeInTheDocument();
});

test('log vacuum plot excludes nonpositive values and limits ticks across extreme finite ranges', () => {
  const time = Date.now();
  render(<SupervisionMonitor telemetry={telemetry} vacuumSamples={[
    { time: time - 2000, session: 'a', receipt: '1', 'vide:14': 1e-300 },
    { time: time - 1000, session: 'a', receipt: '2', 'vide:14': -1 },
    { time, session: 'a', receipt: '3', 'vide:14': 1e300 },
  ]} />);
  const graph = screen.getByRole('img', { name: 'Historique pression · échelle logarithmique mbar' });
  expect(within(graph).getAllByTestId('vacuum-log-tick').length).toBeLessThanOrEqual(6);
  expect(within(graph).getByTestId('vacuum-plot')).toHaveAttribute('height', '220');
  const paths = [...graph.querySelectorAll('path')].map((path) => path.getAttribute('d')).join(' ');
  expect(paths).not.toMatch(/NaN|Infinity|L/);
  expect(graph.querySelectorAll('circle')).toHaveLength(2);
});

test('signed current pressures stay visible and flagged; only positive history is plotted', () => {
  const data = Array(64).fill(0.0052); data[10] = 8.5e-10; data[11] = 0;
  const live = { failure: '', elapsed: 0, payload: { snapshot: { publications: {
    'VAM-A': { data, stale: false, age_seconds: .1, error: { status: false, code: 0 },
      lv_type: { type: 'Cluster', name: 'VAM-A', fields: Array(64).fill({ type: 'DBL' }) } },
  } } } };
  const time = Date.now();
  render(<SupervisionMonitor telemetry={live} vacuumSamples={[
    { time: time - 1000, session: 'a', 'vide:5': -4.3e-9, 'vide:14': 8e-10 },
    { time, session: 'a', 'vide:5': -4.2e-9, 'vide:14': 8.5e-10 },
  ]} />);
  expect(screen.getByLabelText('Pressions hors échelle logarithmique')).toHaveTextContent('6 négatives · 1 nulle · hors log');
  expect(screen.getByLabelText('Vide permanent · CANON')).toHaveTextContent('-4,3');
  expect(screen.getByLabelText('Vide permanent · CANON')).toHaveAttribute('title', expect.stringContaining('VAM-A[13]'));
  const graph = screen.getByRole('img', { name: 'Historique pression · échelle logarithmique mbar' });
  const paths = [...graph.querySelectorAll('path')].map((path) => path.getAttribute('d'));
  expect(paths.filter(Boolean)).toHaveLength(1);
  expect(paths.find(Boolean)).toContain('L');
  expect(screen.getByLabelText('Courbes de pression')).toHaveTextContent('TPG300 SECTION');
});

test('freshness ticks still update readouts without rebuilding historical SVG geometry', () => {
  const read = jest.fn(() => 1e-7);
  const samples = [{ time: Date.now(), session: 'a', receipt: '1', get 'vide:14'() { return read(); } }];
  const view = render(<SupervisionMonitor telemetry={telemetry} vacuumSamples={samples} />);
  expect(read).toHaveBeenCalled();
  read.mockClear();
  view.rerender(<SupervisionMonitor telemetry={{ ...telemetry, elapsed: 2.25 }} vacuumSamples={samples} />);
  expect(read).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/Vide permanent · Sas Guide HF/)).toHaveTextContent('—');
});
