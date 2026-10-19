import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { BeamLinePanel, SynopticPanel, NewFocusPanel, EthernetCameraPanel, lineValue, lineNumber } from './SupervisionWorkspace';
import workspace from './elyseSupervisionWorkspace.json';
import Elyse from './Elyse';
import LiveSupervision from './LiveSupervision';

function telemetry() {
  const publications = Object.fromEntries([['C1NI6071E', 64], ['C6NI6703', 10], ['C7NI6703', 10], ['C8NI6703', 10]]
    .map(([name, size]) => [name, { data: Array(size).fill(0), age_seconds: 0.1, stale: false,
      error: { status: false, code: 0 }, lv_type: { type: 'Cluster', name, fields: Array(size).fill({ type: 'DBL' }) } }]));
  publications.C7NI6703.data[8] = 4.5;
  publications.C1NI6071E.data[28] = 4.25;
  publications.C1NI6071E.data[34] = 1.25;
  return { payload: { schema_version: 1, execution_allowed: false, server_state: 'ON', quality: 'FRESH',
    expected_banks: Object.keys(publications), stale_after_seconds: 2, error_banks: [],
    snapshot: { receiver_session: 'workspace-session', received_this_process: 27, publications } }, failure: '', elapsed: 0 };
}

test.each([['direct', 'Voie directe', 11], ['deviated', 'Voie déviée', 9]])(
  '%s line keeps native control blocks and no command authority', (line, title, rows) => {
    render(<BeamLinePanel line={line} telemetry={telemetry()} />);
    expect(screen.getByRole('region', { name: title, exact: true })).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(rows * 6);
    screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
    expect(screen.getAllByRole('img')).toHaveLength(rows * 3);
    expect(screen.getAllByRole('status')).toHaveLength(rows * 2);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  },
);

test('ACQ command and measured readback remain distinct, become unavailable independently', () => {
  const t = telemetry();
  const view = render(<BeamLinePanel line="direct" telemetry={t} />);
  expect(screen.getByLabelText('Dipôle 1 · Consigne ACQ')).toHaveTextContent('4,50');
  expect(screen.getByLabelText('Dipôle 1 · Lecture')).toHaveTextContent('4,25');
  t.payload.snapshot.publications.C7NI6703.stale = true;
  view.rerender(<BeamLinePanel line="direct" telemetry={t} />);
  expect(screen.getByLabelText('Dipôle 1 · Consigne ACQ')).toHaveTextContent('—');
  expect(screen.getByLabelText('Dipôle 1 · Lecture')).toHaveTextContent('4,25');
  t.elapsed = 2;
  view.rerender(<BeamLinePanel line="direct" telemetry={t} />);
  expect(screen.getByLabelText('Dipôle 1 · Lecture')).toHaveTextContent('—');
});

test.each(['OFF', 'FAULT'])('receiver %s hides retained line values even before bank age expires', (state) => {
  const t = telemetry();
  t.payload.server_state = state;
  t.payload.quality = 'RECEIVER_NOT_READY';
  render(<BeamLinePanel line="direct" telemetry={t} />);
  expect(screen.getByLabelText('Dipôle 1 · Consigne ACQ')).toHaveTextContent('—');
  expect(screen.getByLabelText('Dipôle 1 · Lecture')).toHaveTextContent('—');
  screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
});

test('native H5/V5 duplicate readback is not silently corrected', () => {
  render(<BeamLinePanel line="deviated" telemetry={telemetry()} />);
  expect(screen.getByLabelText('Correcteur H5 · Lecture')).toHaveTextContent('1,25');
  expect(screen.getByLabelText('Correcteur V5 · Lecture')).toHaveTextContent('1,25');
});

test('wrong command bank type never passes as a setpoint', () => {
  const t = telemetry(); t.payload.snapshot.publications.C6NI6703.lv_type.name = 'other';
  expect(lineValue({ bank: 'C6NI6703', index: 0 }, t)).toMatchObject({ quality: 'SCHEMA_ERROR', value: null });
});

test('direct-line DOM order follows the original physical grid, not cluster data order', () => {
  render(<BeamLinePanel line="direct" />);
  expect(screen.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent)).toEqual([
    'Phase HF / Laser', 'Focale', 'Dipôle 1', 'Correcteur H1', 'Triplet 1-1', 'Correcteur H2',
    'Correcteur H3', 'Correcteur V1', 'Triplet 1-2', 'Correcteur V2', 'Correcteur V3',
  ]);
  expect(screen.getByRole('region', { name: 'Correcteur H1', exact: true })).toHaveStyle({ gridColumn: '1', gridRow: '2' });
  expect(screen.getByRole('region', { name: 'Correcteur V1', exact: true })).toHaveStyle({ gridColumn: '1', gridRow: '3' });
});

test('native range labels are annotations, not invented live state or applied current clamps', () => {
  const t = telemetry(); t.payload.snapshot.publications.C6NI6703.data[0] = 6.25;
  render(<BeamLinePanel line="direct" telemetry={t} />);
  const corrector = within(screen.getByRole('region', { name: 'Correcteur H1', exact: true }));
  expect(corrector.getByText('-5A à 5A')).toBeInTheDocument();
  expect(corrector.getByLabelText('Correcteur H1 · Consigne ACQ')).toHaveTextContent('6,25');
  expect(corrector.getByLabelText('Correcteur H1 · M/A')).toHaveTextContent('M/A');
  expect(corrector.getByLabelText('Correcteur H1 · X1 / X10')).toHaveTextContent('X1/X10');
  expect(within(screen.getByRole('region', { name: 'Phase HF / Laser', exact: true })).getByText('0 à 360°')).toBeInTheDocument();
});

test.each(['direct', 'deviated'])('%s corrector buttons retain native identities and distinct purposes', (line) => {
  render(<BeamLinePanel line={line} />);
  const rows = workspace.lines[line].rows.filter((row) => row.label.startsWith('Correcteur'));
  rows.forEach((row) => {
    const block = within(screen.getByRole('region', { name: row.label, exact: true }));
    const buttons = block.getAllByRole('button');
    expect(buttons.map((button) => button.textContent)).toEqual(['M/A', 'X1/X10', '<<', '<', '>', '>>']);
    expect(buttons.map((button) => button.dataset.nativeUid)).toEqual(row.native_buttons.map((control) => control.native_uid));
    expect(buttons.map((button) => Number(button.dataset.actionCode))).toEqual([1, 16, 128, 256, 512, 1024]);
    expect(buttons[0]).toHaveAccessibleName(`${row.label} · M/A`);
    expect(buttons[0].title).toContain('Valeurs conservées dans les branches auditées');
    expect(buttons[0].title).toContain('aucune commande matérielle Marche / Arrêt démontrée');
    expect(buttons[0].title).toContain('banques analogiques peuvent être republiées');
    expect(buttons[1].title).toContain('pas de réglage');
    expect(buttons[2].title).toContain('Diminuer la consigne — grand pas : 0,1 ou 1 A');
    expect(buttons[3].title).toContain('Diminuer la consigne — petit pas : 0,01 ou 0,1 A');
    expect(buttons[4].title).toContain('Augmenter la consigne — petit pas : 0,01 ou 0,1 A');
    expect(buttons[5].title).toContain('Augmenter la consigne — grand pas : 0,1 ou 1 A');
    buttons.forEach((button) => {
      expect(button).toBeDisabled();
      expect(button).not.toHaveAttribute('aria-pressed');
      expect(button.title).toContain('Commande non connectée');
      fireEvent.click(button);
    });
    expect(block.getByLabelText(`${row.label} · Consigne ACQ`)).toHaveTextContent('—');
  });
});

test('fixed numeric formats preserve the distinct native precisions of individual blocks', () => {
  expect(lineNumber(1.234, '%.2f')).toBe('1,23');
  expect(lineNumber(1.234, '%.1f')).toBe('1,2');
  expect(lineNumber(1.234, '%.0f')).toBe('1');
  expect(lineNumber(1.234, '%.2g')).toBe('1,2');
});

test('Synoptic uses the original static image rather than a fabricated equipment-state diagram', () => {
  render(<SynopticPanel />);
  expect(screen.getByRole('img', { name: /Synoptique ELYSE original/ })).toHaveAttribute('src', 'elyse-synoptique-original.png');
  expect(screen.getByText('Plan d’origine · statique')).toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

test('NewFocus holds only local draft configuration and does not zero or move any motor', () => {
  render(<NewFocusPanel />);
  expect(screen.getByLabelText('IP NewFocus')).toHaveValue('');
  fireEvent.change(screen.getByLabelText('IP NewFocus'), { target: { value: '192.0.2.10' } });
  fireEvent.change(screen.getByLabelText('Pas relatifs NewFocus'), { target: { value: '10' } });
  expect(screen.getByText('Non connecté')).toBeInTheDocument();
  expect(screen.getByLabelText('Paire de moteurs NewFocus')).toHaveValue('');
  screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
  expect(screen.getByLabelText('Compteur moteur 1')).toHaveTextContent('—');
});

test('Ethernet camera contains no IMAQ control, fake image or automatic URL fetch', () => {
  render(<EthernetCameraPanel />);
  fireEvent.change(screen.getByLabelText('Adresse caméra Ethernet'), { target: { value: '192.0.2.20' } });
  expect(screen.getByRole('img', { name: 'Aucune image caméra reçue' }).tagName).toBe('DIV');
  expect(screen.queryByText(/IMAQ|NI1409/)).not.toBeInTheDocument();
  expect(screen.getByText('Non connectée')).toBeInTheDocument();
  screen.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
});

test.each(['synoptique', 'newfocus', 'camera'])('%s has no unrelated Acquisition alarm', (tab) => {
  render(<LiveSupervision tab={tab} telemetry={{ payload: null, failure: 'Acquisition unavailable', elapsed: 0 }} />);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('operator tabs remove retired pages and share the single readonly telemetry stream', async () => {
  const client = { telemetry: jest.fn().mockResolvedValue(telemetry().payload),
    snapshot: jest.fn().mockResolvedValue({ dps_fields: [], pages: {}, display_fields: {} }),
    replay: jest.fn(), stageIntent: jest.fn(), submitIntent: jest.fn() };
  render(<Elyse client={client} />);
  await screen.findByText('Watchdog Acquisition : connecté');
  for (const name of ['Monitoring', 'Programme', 'Variables locales', 'Help', 'IMAQ', 'WCM2', 'WCM5']) {
    expect(screen.queryByRole('tab', { name, exact: true })).not.toBeInTheDocument();
  }
  for (const [name, region] of [['Voie directe', 'Voie directe'], ['Voie déviée', 'Voie déviée'],
    ['Synoptique ELYSE', 'Synoptique ELYSE'], ['NewFocus', 'NewFocus Picomotor'], ['Caméra Ethernet', 'Caméra Ethernet']]) {
    fireEvent.click(screen.getByRole('tab', { name, exact: true }));
    expect(screen.getByRole('region', { name: region, exact: true })).toBeInTheDocument();
    expect(within(screen.getByRole('tabpanel', { name, exact: true })).queryByRole('heading', { name: 'Vide · dernières valeurs' })).not.toBeInTheDocument();
  }
  expect(client.telemetry).toHaveBeenCalledTimes(1);
  expect(client.replay).not.toHaveBeenCalled();
  expect(client.stageIntent).not.toHaveBeenCalled();
  expect(client.submitIntent).not.toHaveBeenCalled();
});
