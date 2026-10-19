import React from 'react';
import { render, screen, within } from '@testing-library/react';
import FluidesPanel, { fluidesValve, FluidesTemperatureChart } from './FluidesPanel';
import { emptyTrend } from './fluidesTrend';

function telemetry() {
  const publications = Object.fromEntries([['C1NI6071E', 64, 'DBL'], ['C3_IN_DIO96', 56, 'Boolean'], ['C4_IN_DIO96', 64, 'Boolean']]
    .map(([name, size, type]) => [name, { data: Array(size).fill(type === 'DBL' ? 0 : true),
      age_seconds: 0.1, stale: false, error: { status: false, code: 0 },
      lv_type: { type: 'Cluster', name, fields: Array(size).fill({ type }) } }]));
  publications.C1NI6071E.data[0] = 20.5; publications.C1NI6071E.data[8] = 20.9;
  return { payload: { stale_after_seconds: 2, snapshot: { publications } }, elapsed: 0, failure: '' };
}

test('matches native groups and per-field colors without guessing missing live setpoints', () => {
  const t = telemetry();
  t.payload.snapshot.publications.C4_IN_DIO96.data.fill(false);
  render(<FluidesPanel telemetry={t} trend={emptyTrend()} />);
  expect(screen.getByRole('region', { name: 'Fluides CANON' })).toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Fluides SECTION' })).toBeInTheDocument();
  expect(screen.getByLabelText('Canon 220V · true')).toHaveStyle({ backgroundColor: '#FF3333' });
  expect(screen.getByLabelText('Canon Pressostat · true')).toHaveStyle({ backgroundColor: '#00C82D' });
  expect(screen.getByLabelText('Canon Défauts · true')).toHaveTextContent('AUCUN DEFAUT');
  expect(screen.getByLabelText('Canon débimètre · false')).toHaveStyle({ backgroundColor: '#00C82D' });
  expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('20,5');
  expect(screen.getByLabelText('Température SECTION · lecture')).toHaveTextContent('20,9');
  expect(screen.getByLabelText('EAU FOCALE · non transmise')).toHaveStyle({ backgroundColor: '#88939e' });
  expect(screen.getAllByText('consigne non transmise')).toHaveLength(2);
  screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
  expect(screen.getAllByRole('button')).toHaveLength(6);
});

test.each([['CANON', 2], ['SECTION', 8]])('reproduces all four wired valve cases independently: %s', (name, index) => {
  const t = telemetry(); const data = t.payload.snapshot.publications.C3_IN_DIO96.data;
  const expected = [['REGULATION', '#00C82D'], ['FERMEE', '#EE9A28'], ['OUVERTE', '#EE9A28'], ['EN DEFAUT', '#FF3333']];
  const actual = expected.map(([text, color], state) => {
    data[index] = Boolean(state & 1); data[index + 1] = Boolean(state & 2);
    const result = fluidesValve(name, t);
    return [result.text, result.color];
  });
  expect(actual).toEqual(expected.map(([text, color]) => [`VANNE ${name}\n${text}`, color]));
});

test.each(['stale', 'schema', 'read', 'http'])('does not leave fresh colors or numeric readouts on failure: %s', (reason) => {
  const t = telemetry();
  if (reason === 'stale') t.elapsed = 2;
  if (reason === 'schema') { t.payload.snapshot.publications.C3_IN_DIO96.data.pop(); t.payload.snapshot.publications.C1NI6071E.data.pop(); }
  if (reason === 'read') { t.payload.snapshot.publications.C3_IN_DIO96.error.code = 7; t.payload.snapshot.publications.C1NI6071E.error.code = 7; }
  if (reason === 'http') t.failure = 'HTTP failed';
  render(<FluidesPanel telemetry={t} trend={emptyTrend()} />);
  expect(screen.getByLabelText('VANNE CANON · INCONNUE')).toHaveStyle({ backgroundColor: '#88939e' });
  expect(screen.getByLabelText('Canon Pressostat · inconnu')).toHaveStyle({ backgroundColor: '#88939e' });
  expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('—');
});

test('chart shows both actual channels from the first point, in one common Celsius scale', () => {
  const view = render(<FluidesTemperatureChart trend={{ samples: [{ time: 100000, canon: 20.5, section: 20.9 }], paused: false }} />);
  const graph = screen.getByRole('img', { name: /CANON et SECTION · 1 points/ });
  expect(within(graph).getByTestId('temperature-canon').getAttribute('d')).toMatch(/^M/);
  expect(screen.getAllByText(/°C ·/)).toHaveLength(2);
  expect(screen.getByText('Échelle commune · °C')).toBeInTheDocument();
  view.rerender(<FluidesTemperatureChart trend={{ samples: [{ time: 100000, canon: 20.5, section: 20.9 },
    { time: 101000, canon: null, section: null }, { time: 102000, canon: 20.6, section: 20.8 }], paused: true }} />);
  expect(screen.getByTestId('temperature-canon').getAttribute('d')).not.toMatch(/L/);
  expect(screen.getByText('Flux interrompu / en attente')).toBeInTheDocument();
});

test('empty chart is explicitly waiting, not a flat invented zero line', () => {
  render(<FluidesTemperatureChart trend={emptyTrend()} />);
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.getByText(/premières températures valides/)).toBeInTheDocument();
  expect(screen.getByText(/Dernières 30 min · maximum 1800 points/)).toHaveTextContent('Buffer RAM');
  expect(screen.getByText(/Dernières 30 min · maximum 1800 points/)).toHaveTextContent('aucun fichier ni base de données');
});
