import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
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
  expect(screen.getAllByText('Consigne')).toHaveLength(2);
  expect(screen.getByLabelText('Consigne CANON')).toHaveTextContent('—');
  expect(screen.getByLabelText('Consigne SECTION')).toHaveTextContent('—');
  screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
  expect(screen.getAllByRole('button')).toHaveLength(6);
});

function withSetpoints() {
  const t = telemetry();
  t.payload.snapshot.publications.C8NI6703 = { data: [0, 20.9, 28.1, 0, 0, 0, 0, 0, 0, 0],
    age_seconds: .1, stale: false, error: { status: false, code: 0 },
    lv_type: { type: 'Cluster', name: 'C8NI6703', fields: Array(10).fill({ type: 'DBL' }) } };
  return t;
}

test('reads transmitted C8 setpoints separately from measured C1 temperatures', () => {
  render(<FluidesPanel telemetry={withSetpoints()} trend={emptyTrend()} />);
  expect(screen.getByLabelText('Consigne CANON')).toHaveTextContent('20,9');
  expect(screen.getByLabelText('Consigne SECTION')).toHaveTextContent('28,1');
  expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('20,5');
  expect(screen.getByLabelText('Température SECTION · lecture')).toHaveTextContent('20,9');
  expect(screen.getByLabelText('Consigne CANON').parentElement).toHaveAttribute('title', expect.stringContaining('C8NI6703[1] · FRESH'));
  screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
});

test.each(['stale', 'read', 'schema', 'type', 'name', 'nonfinite', 'missing'])('does not substitute measured temperature for unavailable setpoint: %s', (reason) => {
  const t = withSetpoints();
  const bank = t.payload.snapshot.publications.C8NI6703;
  if (reason === 'stale') bank.age_seconds = 2;
  if (reason === 'read') bank.error.status = true;
  if (reason === 'schema') bank.data.pop();
  if (reason === 'type') bank.lv_type.fields = Array(10).fill({ type: 'I32' });
  if (reason === 'name') bank.lv_type.name = 'unqualified';
  if (reason === 'nonfinite') { bank.data[1] = NaN; bank.data[2] = Infinity; }
  if (reason === 'missing') delete t.payload.snapshot.publications.C8NI6703;
  render(<FluidesPanel telemetry={t} trend={emptyTrend()} />);
  expect(screen.getByLabelText('Consigne CANON')).toHaveTextContent('—');
  expect(screen.getByLabelText('Consigne SECTION')).toHaveTextContent('—');
  expect(screen.getByLabelText('Température CANON · lecture')).toHaveTextContent('20,5');
});

test('setpoint readouts expire with elapsed time and HTTP failure, retaining a real zero only when fresh', () => {
  const t = withSetpoints(); t.payload.snapshot.publications.C8NI6703.data[1] = 0;
  const view = render(<FluidesPanel telemetry={t} trend={emptyTrend()} />);
  expect(screen.getByLabelText('Consigne CANON')).toHaveTextContent('0,0');
  view.rerender(<FluidesPanel telemetry={{ ...t, elapsed: 2 }} trend={emptyTrend()} />);
  expect(screen.getByLabelText('Consigne CANON')).toHaveTextContent('—');
  view.rerender(<FluidesPanel telemetry={{ ...t, failure: 'offline' }} trend={emptyTrend()} />);
  expect(screen.getByLabelText('Consigne SECTION')).toHaveTextContent('—');
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
  expect(within(graph).getByTestId('temperature-legend')).toBeInTheDocument();
  const plot = within(graph).getByTestId('temperature-plot');
  expect(plot.getAttribute('width')).toBe(plot.getAttribute('height'));
  expect(screen.queryByText('Températures CANON + SECTION')).not.toBeInTheDocument();
  expect(screen.queryByText('Mesures en direct')).not.toBeInTheDocument();
  expect(screen.queryByText(/min · .*points/)).not.toBeInTheDocument();
  view.rerender(<FluidesTemperatureChart trend={{ samples: [{ time: 100000, canon: 20.5, section: 20.9 },
    { time: 101000, canon: null, section: null }, { time: 102000, canon: 20.6, section: 20.8 }], paused: true }} />);
  expect(screen.getByTestId('temperature-canon').getAttribute('d')).not.toMatch(/L/);
  expect(screen.getByText('Flux interrompu / en attente')).toBeInTheDocument();
});

test('empty chart is explicitly waiting, not a flat invented zero line', () => {
  render(<FluidesTemperatureChart trend={emptyTrend()} />);
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.getByText('En attente des températures')).toBeInTheDocument();
  expect(screen.queryByText(/0 points/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Sources et états/)).not.toBeInTheDocument();
});

test('continuous samples are thin connected lines, with small markers only for isolated measurements', () => {
  const samples = Array.from({ length: 100 }, (_, i) => ({ time: 100000 + i * 1000, session: 'a', canon: 20 + i / 100, section: 22 }));
  const view = render(<FluidesTemperatureChart trend={{ samples, paused: false }} />);
  expect(screen.getByTestId('temperature-canon').getAttribute('d')).toContain('L');
  expect(screen.getByTestId('temperature-canon')).toHaveAttribute('stroke-width', '1.6');
  expect(screen.getByTestId('temperature-canon')).toHaveAttribute('vector-effect', 'non-scaling-stroke');
  expect(view.container.querySelectorAll('circle')).toHaveLength(0);
  view.rerender(<FluidesTemperatureChart trend={{ samples: [samples[0], { time: 101000, canon: null, section: null }, samples[2]], paused: false }} />);
  expect(screen.getByTestId('temperature-canon').getAttribute('d')).not.toContain('L');
  expect(view.container.querySelectorAll('circle')).toHaveLength(4);
  view.container.querySelectorAll('circle').forEach((circle) => expect(circle).toHaveAttribute('r', '1.5'));
});

test('keeps history window control and failure states without adding display clutter', () => {
  const change = jest.fn();
  render(<FluidesTemperatureChart trend={{ samples: [], paused: true, error: 'storage unavailable' }}
    windowMinutes={30} onWindowChange={change} />);
  fireEvent.change(screen.getByRole('combobox', { name: 'Durée historique Fluides' }), { target: { value: '60' } });
  expect(change).toHaveBeenCalledWith(60);
  expect(screen.getByText('Flux interrompu / en attente')).toBeInTheDocument();
  expect(screen.getByText('Historique : storage unavailable')).toBeInTheDocument();
});

test('freshness ticks do not rebuild an unchanged curve or construct per-point locale formatters', () => {
  const read = jest.fn(() => 20.5);
  const sample = { time: 100000, get canon() { return read(); }, section: 20.9 };
  const trend = { samples: [sample], paused: false };
  const locale = jest.spyOn(Date.prototype, 'toLocaleTimeString');
  try {
    const view = render(<FluidesTemperatureChart trend={trend} />);
    expect(read).toHaveBeenCalled();
    expect(locale).not.toHaveBeenCalled();
    read.mockClear();
    view.rerender(<FluidesTemperatureChart trend={trend} />);
    expect(read).not.toHaveBeenCalled();
    view.unmount();
  } finally { locale.mockRestore(); }
});
