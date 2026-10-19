import React from 'react';
import { render, screen } from '@testing-library/react';
import VacuumPanel, { nativePlacement, projectVacuumValve } from './VacuumPanel';
import layout from './elyseVacuumPanel.json';

function telemetry() {
  return { elapsed: 0, failure: '', payload: { stale_after_seconds: 2, snapshot: { publications: {
    'VAM-A': { data: Array(64).fill(0.0052), stale: false, age_seconds: 0.1,
      error: { status: false, code: 0 }, lv_type: { type: 'Cluster', name: 'VAM-A', fields: Array(64).fill({ type: 'DBL' }) } },
    C5_IN_DIO96: { data: Array.from({ length: 56 }, (_, i) => [15, 17].includes(i)), stale: false, age_seconds: 0.1,
      error: { status: false, code: 0 }, lv_type: { type: 'Cluster', name: 'C5_IN_DIO96', fields: Array(56).fill({ type: 'Boolean' }) } },
  } } } };
}

test('keeps the observed spatial layout, not the arbitrary source array order', () => {
  const t = telemetry();
  render(<VacuumPanel telemetry={t} />);
  expect(screen.getByRole('region', { name: 'Vide · implantation des capteurs' })).toBeInTheDocument();
  expect(screen.getByLabelText('Sas Guide HF')).toHaveTextContent('-1,0 × 10−8');
  expect(screen.getByLabelText('VANNE CATHODE · OUVERTE')).toHaveStyle({ backgroundColor: '#00C82D' });
  expect(screen.getByLabelText('VANNE INJECTION · OUVERTE')).toHaveStyle({ backgroundColor: '#00C82D' });
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(screen.getAllByRole('status')).toHaveLength(8);
  expect(screen.getAllByText(/sans moyenne native/)).toHaveLength(2);
  const positions = Object.fromEntries(layout.pressures.map((p) => [p.field, p]));
  expect([positions[3].x, positions[5].x, positions[1].x]).toEqual([0, 0, 0]);
  expect(positions[3].y).toBeLessThan(positions[5].y);
  expect(positions[5].y).toBeLessThan(positions[1].y);
  expect(positions[14].x).toBe(positions[7].x);
  expect(positions[14].y).toBeLessThan(positions[7].y);
  expect(positions[7].x).toBeLessThan(positions[12].x);
  expect(positions[12].x).toBeLessThan(positions[9].x);
  expect(positions[9].x).toBeLessThan(positions[17].x);
  expect(screen.getByTestId('vacuum-location-7')).toHaveStyle(nativePlacement(positions[7]));
});

test.each(layout.valves)('maps all four $name states from the exact source bit order', (spec) => {
  const t = telemetry();
  const data = t.payload.snapshot.publications.C5_IN_DIO96.data;
  const states = [0, 1, 2, 3].map((state) => {
    data[spec.indices[0]] = Boolean(state & 1);
    data[spec.indices[1]] = Boolean(state & 2);
    return projectVacuumValve(spec, t);
  });
  expect(states.map((s) => s.text)).toEqual(['ENTROUVERTE', 'OUVERTE', 'FERMEE', 'EN DEFAUT'].map((s) => `VANNE ${spec.name}\n${s}`));
  expect(states.map((s) => s.color)).toEqual(['#FF3333', '#00C82D', '#FF3333', '#FF3333']);
});

test.each(['stale', 'read', 'http'])('does not preserve old open/green valves or pressure values on %s failure', (reason) => {
  const t = telemetry();
  if (reason === 'stale') t.elapsed = 2;
  if (reason === 'read') Object.values(t.payload.snapshot.publications).forEach((b) => { b.error.code = 1; });
  if (reason === 'http') t.failure = 'HTTP failed';
  render(<VacuumPanel telemetry={t} />);
  expect(screen.getByLabelText('VANNE CATHODE · INCONNUE')).toHaveStyle({ backgroundColor: '#88939e' });
  expect(screen.getByLabelText('CANON')).toHaveTextContent('—');
});

test('requires actual 56-bit C5 bank, refusing a tempting 64-field substitute', () => {
  const t = telemetry();
  const bank = t.payload.snapshot.publications.C5_IN_DIO96;
  bank.data.push(...Array(8).fill(false)); bank.lv_type.fields.push(...Array(8).fill({ type: 'Boolean' }));
  expect(projectVacuumValve(layout.valves[0], t).quality).toBe('SCHEMA_ERROR');
});

test('retains spatial locations and valid valve input when pressure bank is missing', () => {
  const t = telemetry(); delete t.payload.snapshot.publications['VAM-A'];
  render(<VacuumPanel telemetry={t} />);
  expect(screen.getAllByRole('status')).toHaveLength(8);
  expect(screen.getByLabelText('CANON')).toHaveTextContent('—');
  expect(screen.getByLabelText('VANNE INJECTION · OUVERTE')).toBeInTheDocument();
});
