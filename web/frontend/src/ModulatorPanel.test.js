import React from 'react';
import { render, screen, within } from '@testing-library/react';
import ModulatorPanel from './ModulatorPanel';

function telemetry() {
  const publications = Object.fromEntries([['C2NI6071E', 64, 'DBL'], ['C4_IN_DIO96', 64, 'Boolean'], ['EPS', 77, 'Boolean']]
    .map(([name, count, type]) => [name, { age_seconds: 0.1, stale: false,
      error: { status: false, code: 0 }, data: Array(count).fill(type === 'Boolean' ? false : 0),
      lv_type: { type: 'LvVariant', contained_type: { type: 'Cluster', name,
        fields: Array(count).fill({ type }) } },
    }]));
  return { payload: { stale_after_seconds: 2, snapshot: { publications } }, elapsed: 0, failure: '' };
}

test('matches native groups, five EPS stages and 14 numeric readouts without command authority', () => {
  const t = telemetry();
  t.payload.snapshot.publications.C2NI6071E.data[16] = -3.45;
  render(<ModulatorPanel telemetry={t} />);
  expect(screen.getByRole('heading', { name: 'MODULATEUR' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'KLYSTRON' })).toBeInTheDocument();
  const stages = screen.getByRole('group', { name: 'Étapes logicielles · EPS' });
  expect(within(stages).getAllByRole('img')).toHaveLength(5);
  expect(screen.getAllByRole('button')).toHaveLength(11);
  screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
  expect(screen.getAllByRole('status')).toHaveLength(14); // output elements
  expect(screen.getByLabelText('V Klystron')).toHaveTextContent('-3,5');
});

test('keeps age and palette explanations inside collapsed diagnostics, not above or below the diagram', () => {
  render(<ModulatorPanel telemetry={telemetry()} />);
  expect(screen.getByText(/LECTURE SEULE · M \/ A et RESET sur Supervision LabVIEW/)).not.toBeVisible();
  expect(screen.getByText(/Couleurs de la palette enregistrée/)).not.toBeVisible();
  expect(screen.getByText('Sources des 48 indicateurs et mesures')).toBeVisible();
  screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
});

test('uses source palette, not a guessed TRUE means OK rule, and EPS changes only its own stage', () => {
  const t = telemetry();
  const view = render(<ModulatorPanel telemetry={t} />);
  expect(screen.getByLabelText('Résistivité · false')).toHaveStyle({ backgroundColor: '#00C82D' });
  expect(screen.getByRole('img', { name: 'GENERAL · OFF' })).toHaveStyle({ backgroundColor: '#1E4B00' });
  t.payload.snapshot.publications.C4_IN_DIO96.data[39] = true;
  t.payload.snapshot.publications.EPS.data[8] = true;
  view.rerender(<ModulatorPanel telemetry={t} />);
  expect(screen.getByLabelText('Résistivité · true')).toHaveStyle({ backgroundColor: '#FF3333' });
  expect(screen.getByRole('img', { name: 'GENERAL · ON' })).toHaveStyle({ backgroundColor: '#64FF00' });
  expect(screen.getByRole('img', { name: 'CHAUFFAGE · OFF' })).toHaveStyle({ backgroundColor: '#1E4B00' });
});

test.each(['stale', 'read-error', 'http-error'])('does not leave stale green lamps visible: %s', (reason) => {
  const t = telemetry();
  t.payload.snapshot.publications.EPS.data[8] = true;
  if (reason === 'stale') t.elapsed = 2;
  else if (reason === 'read-error') t.payload.snapshot.publications.EPS.error.code = 123;
  else t.failure = 'network failed';
  render(<ModulatorPanel telemetry={t} />);
  expect(screen.getByRole('img', { name: 'GENERAL · inconnu' })).toHaveStyle({ backgroundColor: '#88939e' });
  expect(screen.getByLabelText('V Klystron')).toHaveTextContent(reason === 'read-error' ? '0,0' : '—');
});

test('C4 status and C2 measurement remain independent observations', () => {
  const t = telemetry();
  t.payload.snapshot.publications.C4_IN_DIO96.stale = true;
  t.payload.snapshot.publications.C2NI6071E.data[16] = 12.34;
  render(<ModulatorPanel telemetry={t} />);
  expect(screen.getByLabelText('V Klystron · inconnu')).toHaveStyle({ backgroundColor: '#88939e' });
  expect(screen.getByLabelText('V Klystron')).toHaveTextContent('12,3');
});
