import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Elyse, { normalizeSupervisionTab } from './Elyse';
import { elyseSupervisionClient as defaultClient } from './api/elyseSupervisionClient';

beforeEach(() => {
  jest.spyOn(XMLHttpRequest.prototype, 'open').mockImplementation(() => {
    throw new Error('Unmocked HTTP reads are blocked in this offline UI suite.');
  });
});
afterEach(() => jest.restoreAllMocks());

function clientFixture() {
  const snapshot = {
    schema_version: 1, execution_allowed: false,
    dps_fields: ['Marche refroidissement X', 'X Marche GENERAL Mod.'],
    pages: {
      fluides: { page: 'Page Fluides', procedures: ['Marche régulation', 'Arrêt régulation'],
        arrows: [{ arrow: '> Canon', numeric_field: 'T° CANON:', delta: 0.1 }] },
      hf: { page: 'Page HF', procedures: ['Marche att./déph.', 'Arrêt att./déph.'],
        arrows: [{ arrow: '<< Att HF', numeric_field: 'Cons Atténuateur HF', delta: -5 }] },
      ht: { page: 'Page HT', arrows: [], procedures: ['Marche HT'] },
      modulator: { page: 'Page Modulateur', arrows: [], procedures: ['Marche MOD', 'Arrêt MOD'] },
      alimentations: { page: 'Page Alimentations', arrows: [], procedures: ['Marche Aimants.'] },
    },
    display_fields: { modulator: ['GENERAL MOD OK'], radioprotection: ['Porte lourde'], ht: ['V HT'], fluides: ['Canon 220V'] },
    video_controls: { tool_fields: ['zoom 0,5', 'zoom x1', 'zoom x2', 'zoom x3', '250', 'Clear 250'], image_quality: 'UNAVAILABLE' },
    beamline_controls: { diagnostic_stations: ['T1', 'T2', 'T3'], diagnostic_selectors: [0, 1, 2],
      faraday_stations: [1, 2, 3], faraday_tab_selectors: [0, 1, 2, 3],
      faraday_en_inputs: ['Etat Faraday 1 EN', 'Etat Faraday 2 EN', 'Etat Faraday 3 EN'], digital_selectors: [0, 1],
      engineering_units_qualified: false, physical_state_observed: false },
    translator_controls: { selections: [{ value: 1, label: 'LASER' }, { value: 2, label: 'T1' }, { value: 3, label: 'T2' }, { value: 4, label: 'T3' }],
      polling_expression: { measurement_names: ['Position Miroir Laser', 'Etat T1', 'Etat MLaser EN'] }, stop_implementation_allowed: false },
    motion_controls: { jog_labels: ['Move forward X', 'Move reverse X', 'Move forward Y', 'Move reverse Y'], jog_event_indices: [28, 29], error_event_indices: [27, 28, 29],
      autotune_stages: ['CHANNEL3_X', 'CHANNEL3_Y', 'CHANNEL2_X', 'CHANNEL2_Y'], autotune_channels: [2, 3] },
    file_controls: { path_states: [{ value: 'VALID', label: 'valid' }, { value: 'EMPTY', label: 'empty' }, { value: 'NOT_A_PATH', label: 'Not A Path' }],
      load_applies_equipment_preset: false, save_tir_model_status: 'EXCLUDED_BY_USER' },
    registry: { registry_revision: 'test-candidates', entries: [
      { equipment_id: 'corrector-h1', label: 'Correcteur H1', owner: 'DEVICE_SERVER', route: { slot_id: 4 } },
      { equipment_id: 'corrector-h2', label: 'Correcteur H2', owner: 'UNKNOWN', route: null },
    ] },
    source_integrity: { matches: false },
    coverage: { bounded_event_indices: 34, events: [{ event_index: 1, label: 'Fréquence machine', boundary: 'PSP blocked' }] },
  };
  return {
    snapshot: jest.fn().mockResolvedValue(snapshot),
    replay: jest.fn().mockResolvedValue({ schema_version: 1, execution_allowed: false,
      physical_status: 'NOT_EXECUTED', operation: 'machine_frequency', result: { projected_numeric: 1.1 } }),
  };
}
async function loaded(client = clientFixture()) {
  const view = render(<Elyse client={client} />);
  await screen.findByText('MODÈLES PYTHON · REJEU UNIQUEMENT · AUCUNE COMMANDE TRANSMISE');
  return { client, ...view };
}

test('live operator diagnostics keeps the rich shell and nests native panels without actuator dispatch', async () => {
  const client = clientFixture();
  client.telemetry = jest.fn().mockResolvedValue({ quality: 'WAITING', snapshot: { publications: {} } });
  client.history = jest.fn().mockResolvedValue({ storage: 'server_sqlite', samples: [] });
  const diagnostics = { snapshot: jest.fn().mockResolvedValue({ schema_version: 1,
    execution_allowed: false, hardware_writes: false, cameras: [] }) };
  const video = { video: jest.fn().mockResolvedValue({ schema_version: 1, owner: 'supervision',
    available: false, stale: true, frame: null }) };
  const { unmount } = render(<Elyse client={client} diagnosticsClient={diagnostics} videoClient={video} />);
  await waitFor(() => expect(client.snapshot).toHaveBeenCalled());
  for (const name of ['Vide', 'Synchro', 'Fluides', 'Modulateur', 'HT / HF / Alim / RP', 'Caméra NI1409']) {
    expect(screen.getByRole('tab', { name, exact: true })).toBeInTheDocument();
  }
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  const tabs = screen.getByRole('tablist', { name: 'Onglets diagnostics SuperVision' });
  expect(within(tabs).getAllByRole('tab').map((button) => button.textContent))
    .toEqual(['Centroïde', 'Profils X Y', 'Diag', 'WCM', 'Beam profile']);
  fireEvent.click(within(tabs).getByRole('tab', { name: 'Diag', exact: true }));
  expect(screen.getByRole('tablist', { name: 'Panneaux Laser / translateurs' })).toBeInTheDocument();
  expect(screen.getByRole('tablist', { name: 'Panneaux Cages de Faraday' })).toBeInTheDocument();
  expect(screen.getByRole('tablist', { name: 'Panneaux Fente' })).toBeInTheDocument();
  expect(screen.getByText('Prévisualisations historiques')).toBeInTheDocument();
  expect(client.replay).not.toHaveBeenCalled();
  expect(video.video).toHaveBeenCalled();
  expect(diagnostics.snapshot).toHaveBeenCalled();
  unmount();
});

test('journal tab opens database history without replay or equipment commands', async () => {
  const client = clientFixture();
  client.errorJournal = jest.fn().mockResolvedValue({ storage: 'server_sqlite', events: [], days: [],
    observed_utc: '2026-10-26T12:00:00Z', sources: [], observer_running: false });
  await loaded(client);
  fireEvent.click(screen.getByRole('tab', { name: 'Journal des alarmes', exact: true }));
  expect(await screen.findByText('Journal des erreurs et alarmes')).toBeInTheDocument();
  expect(client.errorJournal).toHaveBeenCalled();
  expect(client.replay).not.toHaveBeenCalled();
});

test.each(['Vide', 'Fluides', 'Modulateur', 'HT / HF / Alim / RP'])('restores last %s page after leaving and reopening Elyse', async (name) => {
  localStorage.clear();
  const client = clientFixture();
  const first = render(<Elyse client={client} persistUi />);
  await screen.findByText('MODÈLES PYTHON · REJEU UNIQUEMENT · AUCUNE COMMANDE TRANSMISE');
  fireEvent.click(screen.getByRole('tab', { name, exact: true }));
  first.unmount();
  const reopened = render(<Elyse client={client} persistUi />);
  try {
    await screen.findByText('MODÈLES PYTHON · REJEU UNIQUEMENT · AUCUNE COMMANDE TRANSMISE');
    expect(screen.getByRole('tab', { name, exact: true })).toHaveAttribute('aria-selected', 'true');
    expect(client.replay).not.toHaveBeenCalled();
  } finally { reopened.unmount(); localStorage.clear(); }
});

test('restores three navigation levels but never restores command drafts or scenario DPS', async () => {
  localStorage.clear();
  const client = clientFixture();
  const first = render(<Elyse client={client} persistUi />);
  await screen.findByText('MODÈLES PYTHON · REJEU UNIQUEMENT · AUCUNE COMMANDE TRANSMISE');
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO' }));
  fireEvent.click(screen.getByRole('tab', { name: 'Diag', exact: true }));
  const lineTabs = screen.getByRole('tablist', { name: 'Rejeu ligne faisceau' });
  fireEvent.click(within(lineTabs).getByRole('tab', { name: 'T1–T3', exact: true }));
  fireEvent.change(screen.getByLabelText('Station diagnostique'), { target: { value: 'T2' } });
  fireEvent.click(screen.getByRole('checkbox', { name: 'Marche refroidissement X' }));
  // The same nested section survives changing to another main page.
  fireEvent.click(screen.getByRole('tab', { name: 'Fluides', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO' }));
  expect(screen.getByRole('tab', { name: 'Diag', exact: true })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tab', { name: 'T1–T3', exact: true })).toHaveAttribute('aria-selected', 'true');
  first.unmount();
  const reopened = render(<Elyse client={client} persistUi />);
  try {
    await screen.findByText('MODÈLES PYTHON · REJEU UNIQUEMENT · AUCUNE COMMANDE TRANSMISE');
    expect(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Diag', exact: true })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'T1–T3', exact: true })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText('Station diagnostique')).toHaveValue('');
    expect(screen.getByRole('checkbox', { name: 'Marche refroidissement X' })).not.toBeChecked();
    expect(client.replay).not.toHaveBeenCalled();
  } finally { reopened.unmount(); localStorage.clear(); }
});

test('remembers independent diagnostic subpages without mixing Faraday station defaults', async () => {
  localStorage.clear();
  const client = clientFixture();
  const view = render(<Elyse client={client} persistUi />);
  try {
    await screen.findByText('MODÈLES PYTHON · REJEU UNIQUEMENT · AUCUNE COMMANDE TRANSMISE');
    fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO' }));
    fireEvent.click(screen.getByRole('tab', { name: 'Vidéo', exact: true }));
    fireEvent.click(screen.getByRole('tab', { name: 'Caméra', exact: true }));
    fireEvent.click(screen.getByRole('tab', { name: 'Faraday 2', exact: true }));
    expect(screen.getByLabelText('Station Faraday')).toHaveValue('2');
    fireEvent.click(screen.getByRole('tab', { name: 'Faraday 3', exact: true }));
    expect(screen.getByLabelText('Station Faraday')).toHaveValue('3');
    fireEvent.click(screen.getByRole('tab', { name: 'Vidéo', exact: true }));
    expect(screen.getByRole('tab', { name: 'Caméra', exact: true })).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByRole('tab', { name: 'Fluides', exact: true }));
    fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO' }));
    expect(screen.getByRole('tab', { name: 'Vidéo', exact: true })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Caméra', exact: true })).toHaveAttribute('aria-selected', 'true');
    expect(client.replay).not.toHaveBeenCalled();
  } finally { view.unmount(); localStorage.clear(); }
});

test('keeps familiar tabs but removes the entire shot and machine-command rail', async () => {
  await loaded();
  expect(screen.getByText('ELYSE')).toBeInTheDocument();
  expect(screen.getByRole('tablist', { name: 'Pages SuperVision' })).toBeInTheDocument();
  expect(screen.queryByRole('complementary', { name: 'Commandes générales ELYSE' })).not.toBeInTheDocument();
  expect(screen.getByRole('complementary', { name: 'Réglages rapides ELYSE' })).toBeInTheDocument();
  for (const label of ['Vide', 'Synchro', 'Fluides', 'Modulateur', 'HT / HF / Alim / RP', 'Voie directe', 'Voie déviée', 'Synoptique ELYSE', 'NewFocus', 'Caméra Ethernet']) {
    expect(screen.getByRole('tab', { name: label, exact: true })).toBeInTheDocument();
  }
  for (const label of ['TIR', 'PRE-TIR', 'VEILLE', 'ARRÊT', 'LOAD TIR', 'SAVE TIR', 'STOP']) {
    expect(screen.queryByRole('button', { name: label, exact: true })).not.toBeInTheDocument();
  }
  expect(screen.queryByText('Tir en cours')).not.toBeInTheDocument();
  expect(screen.queryByText(/STOP web non connecté/)).not.toBeInTheDocument();
  expect(screen.getByRole('status', { name: 'Watchdog Acquisition' })).toHaveTextContent('en attente');
  expect(screen.getByRole('combobox', { name: 'Fréquence machine' })).toHaveValue('');
});

test.each(['ht', 'hf', 'alimentations', 'radioprotection'])('restores former %s tab into the combined machine page', (saved) => {
  expect(normalizeSupervisionTab(saved)).toBe('machine');
});

test('combined page replaces all four old main tabs without issuing a replay', async () => {
  const { client } = await loaded();
  for (const name of ['HT', 'HF', 'Alimentations', 'Radioprotection']) {
    expect(screen.queryByRole('tab', { name, exact: true })).not.toBeInTheDocument();
  }
  fireEvent.click(screen.getByRole('tab', { name: 'HT / HF / Alim / RP', exact: true }));
  expect(screen.getByRole('tabpanel', { name: 'HT / HF / Alim / RP' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Prévisualiser consignes aimants' })).toBeInTheDocument();
  expect(client.replay).not.toHaveBeenCalled();
});

test('persisted HF selection opens all four live cards without restoring command authority', async () => {
  localStorage.setItem('elyse.supervision.tab', 'hf');
  jest.spyOn(defaultClient, 'snapshot').mockResolvedValue(await clientFixture().snapshot());
  jest.spyOn(defaultClient, 'telemetry').mockResolvedValue({ quality: 'WAITING', snapshot: { publications: {} } });
  jest.spyOn(defaultClient, 'history').mockResolvedValue({ storage: 'server_sqlite', samples: [] });
  const stage = jest.spyOn(defaultClient, 'stageIntent');
  const submit = jest.spyOn(defaultClient, 'submitIntent');
  const replay = jest.spyOn(defaultClient, 'replay');
  const view = render(<Elyse />);
  try {
    await waitFor(() => expect(defaultClient.snapshot).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('tab', { name: 'HT / HF / Alim / RP' })).toHaveAttribute('aria-selected', 'true');
    expect(localStorage.getItem('elyse.supervision.tab')).toBe('machine');
    for (const name of ['HT', 'HF', 'Alimentations', 'Radioprotection']) {
      expect(screen.getByRole('region', { name: `${name} · lecture seule` })).toBeInTheDocument();
    }
    const machine = screen.getByRole('region', { name: 'HT, HF, alimentations et radioprotection' });
    within(machine).getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
    expect(stage).not.toHaveBeenCalled();
    expect(submit).not.toHaveBeenCalled();
    expect(replay).not.toHaveBeenCalled();
  } finally {
    view.unmount(); jest.restoreAllMocks(); localStorage.clear();
  }
});

test('keeps laser image, profiles and vacuum permanently before the control workspace', async () => {
  await loaded();
  const monitor = screen.getByRole('complementary', { name: 'Moniteur permanent ELYSE' });
  expect(within(monitor).getByRole('region', { name: 'Image laser permanente' })).toBeInTheDocument();
  expect(within(monitor).getByRole('region', { name: 'Contours et profils laser permanents' })).toBeInTheDocument();
  expect(within(monitor).getByRole('region', { name: 'Vide · graphique permanent' })).toBeInTheDocument();
  expect(monitor.compareDocumentPosition(screen.getByRole('main')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.queryByRole('tab', { name: 'Beam profile', exact: true })).not.toBeInTheDocument();
  expect(screen.queryByRole('tab', { name: 'WCM', exact: true })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  for (const label of ['Diaphragmes', 'LASER', 'Translateurs', 'Position', 'FISO', 'Faraday 1', 'Faraday 2', 'Faraday 3']) {
    expect(within(screen.getByRole('tablist', { name: 'Diagnostics faisceau' })).getByRole('tab', { name: label, exact: true })).toBeInTheDocument();
  }
});

test.each([1, 2, 3])('Faraday %s has its own correctly selected station without sending an operation', async (station) => {
  const { client } = await loaded();
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: `Faraday ${station}`, exact: true }));
  expect(screen.getByLabelText('Station Faraday')).toHaveValue(String(station));
  expect(client.replay).not.toHaveBeenCalled();
});

test('retired business selection falls back without loading or resubmitting operator intents', async () => {
  localStorage.setItem('elyse.supervision.tab', 'business');
  jest.spyOn(defaultClient, 'snapshot').mockResolvedValue(await clientFixture().snapshot());
  jest.spyOn(defaultClient, 'telemetry').mockResolvedValue({ quality: 'WAITING', snapshot: { publications: {} } });
  jest.spyOn(defaultClient, 'history').mockResolvedValue({ storage: 'server_sqlite', samples: [] });
  const business = jest.spyOn(defaultClient, 'business');
  const stage = jest.spyOn(defaultClient, 'stageIntent');
  const submit = jest.spyOn(defaultClient, 'submitIntent');
  const view = render(<Elyse />);
  try {
    await waitFor(() => expect(defaultClient.snapshot).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('tab', { name: 'Synchro', exact: true })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByRole('tab', { name: 'Supervision / ACQ', exact: true })).not.toBeInTheDocument();
    expect(business).not.toHaveBeenCalled();
    expect(stage).not.toHaveBeenCalled();
    expect(submit).not.toHaveBeenCalled();
  } finally {
    view.unmount(); jest.restoreAllMocks(); localStorage.clear();
  }
});

test('frequency preview calls the backend with an explicit integer', async () => {
  const { client } = await loaded();
  fireEvent.change(screen.getByLabelText(/Fréquence machine · sélecteur/), { target: { value: '5' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser fréquence' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('machine_frequency', { new_value: 5 }, expect.any(AbortSignal)));
  expect(await screen.findByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('NOT_EXECUTED');
});

test('blank numeric input is rejected instead of coerced to zero', async () => {
  const { client } = await loaded();
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser fréquence' }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('Sélecteur entier explicite requis'));
  expect(client.replay).not.toHaveBeenCalled();
});

test('parameter arrow uses server-provided metadata and returned projection', async () => {
  const { client } = await loaded();
  fireEvent.click(screen.getByRole('tab', { name: 'Fluides', exact: true }));
  fireEvent.change(screen.getByLabelText('T° CANON:'), { target: { value: '1' } });
  fireEvent.click(screen.getByRole('button', { name: '> Canon' }));
  await waitFor(() => expect(screen.getByLabelText('T° CANON:')).toHaveValue(1.1));
  expect(client.replay).toHaveBeenCalledWith('parameter_page', {
    page: 'Page Fluides', current_dps: { 'Marche refroidissement X': false, 'X Marche GENERAL Mod.': false },
    arrows: { '> Canon': true }, procedures: { 'Marche régulation': false, 'Arrêt régulation': false },
    numeric_newval: { 'T° CANON:': 1 },
  }, expect.any(AbortSignal));
});

test('command passes the supplied busy DPS bank; browser does not invent arbitration', async () => {
  const { client } = await loaded();
  fireEvent.click(screen.getByText('DPS · scénario fourni'));
  fireEvent.click(screen.getByLabelText('Marche refroidissement X'));
  fireEvent.click(screen.getByRole('tab', { name: 'Modulateur', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Marche MOD', exact: true }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('page_command', {
    page: 'Page Modulateur', current_dps: { 'Marche refroidissement X': true, 'X Marche GENERAL Mod.': false },
    newval: { 'Marche MOD': true, 'Arrêt MOD': false },
  }, expect.any(AbortSignal)));
});

test('magnet page keeps owner split and typed absolute-current preview', async () => {
  const { client } = await loaded();
  fireEvent.click(screen.getByRole('tab', { name: 'HT / HF / Alim / RP', exact: true }));
  expect(screen.getByText('Device Server')).toBeInTheDocument();
  expect(screen.getByText('À qualifier')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Brouillon Correcteur H1'), { target: { value: '0.25' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser consignes aimants' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('magnet_currents', {
    expected_revision: 'test-candidates', idempotency_key: 'web-replay',
    requests: [{ equipment_id: 'corrector-h1', current_a: 0.25 }],
  }, expect.any(AbortSignal)));
});

test('pending replay disables edits and aborts on unmount', async () => {
  const client = clientFixture();
  let resolve;
  client.replay.mockImplementation(() => new Promise((done) => { resolve = done; }));
  const { unmount } = await loaded(client);
  fireEvent.change(screen.getByLabelText(/Fréquence machine · sélecteur/), { target: { value: '5' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser fréquence' }));
  expect(screen.getByRole('button', { name: 'Prévisualiser fréquence' })).toBeDisabled();
  const signal = client.replay.mock.calls[0][2];
  unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => resolve({ result: {} }));
});

test('backend failures remain unavailable; no demo fallback', async () => {
  const client = clientFixture();
  client.snapshot.mockRejectedValue(new Error('unavailable'));
  render(<Elyse client={client} />);
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('Backend indisponible'));
  expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('unavailable');
  expect(screen.getByRole('button', { name: 'Prévisualiser fréquence' })).toBeDisabled();
});

test('removes files, journal and permanent diagnostic workspace from operating pages', async () => {
  const { client } = await loaded();
  expect(screen.queryByText('Fichiers et journal')).not.toBeInTheDocument();
  for (const name of ['Fichiers', 'Messages', 'Rapport', 'Centroïde', 'Faraday 1']) {
    expect(screen.queryByRole('tab', { name, exact: true })).not.toBeInTheDocument();
  }
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  expect(screen.getByRole('tabpanel', { name: 'Contrôle / Diagnostics / FISO' })).toBeInTheDocument();
  expect(screen.getByRole('tab', { name: 'Centroïde', exact: true })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'Fluides', exact: true }));
  expect(screen.queryByRole('tab', { name: 'Centroïde', exact: true })).not.toBeInTheDocument();
  expect(client.replay).not.toHaveBeenCalled();
});

test('retired Monitoring page cannot trigger its old replayer', async () => {
  const { client } = await loaded();
  expect(screen.queryByRole('tab', { name: 'Monitoring', exact: true })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Entrées JSON · monitoring')).not.toBeInTheDocument();
  expect(client.replay).not.toHaveBeenCalled();
});

function chooseCameraScenario(status = 'false', code = '0', source = '') {
  fireEvent.change(screen.getByLabelText('Scénario erreur caméra'), { target: { value: status } });
  fireEvent.change(screen.getByLabelText('Code erreur caméra'), { target: { value: code } });
  fireEvent.change(screen.getByLabelText('Source erreur caméra'), { target: { value: source } });
}

test('video tools require an explicit error scenario instead of assuming driver success', async () => {
  const { client } = await loaded();
  fireEvent.click(screen.getByRole('tab', { name: 'Vide', exact: true }));
  expect(screen.getByRole('region', { name: 'Caméra SuperVision' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'SAVE IMG', exact: true })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'RESET', exact: true })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'zoom x3', exact: true }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('aucun succès pilote supposé'));
  expect(client.replay).not.toHaveBeenCalled();
  chooseCameraScenario('false', '');
  fireEvent.click(screen.getByRole('button', { name: 'zoom x3', exact: true }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('Entier I32 explicite requis'));
  expect(client.replay).not.toHaveBeenCalled();
});

test('zoom uses ordered native metadata and renders Python x3-to-4 intent, not a fake image', async () => {
  const client = clientFixture();
  client.replay.mockResolvedValue({ schema_version: 1, execution_allowed: false, physical_status: 'NOT_EXECUTED', operation: 'video_tools',
    result: { selected_case: 8, branch_properties: [{ control: 'SOURCE', property: 'X Zoom', value: 4 }] } });
  await loaded(client);
  fireEvent.click(screen.getByRole('tab', { name: 'Vide', exact: true }));
  chooseCameraScenario();
  fireEvent.click(screen.getByRole('button', { name: 'zoom x3', exact: true }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('video_tools', {
    values: [false, false, false, true, false, false], final_property_error: { status: false, code: 0, source: '' },
  }, expect.any(AbortSignal)));
  expect(await screen.findByText('SOURCE · X Zoom = 4')).toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Caméra SuperVision' })).toBeInTheDocument();
  expect(screen.getByText('Intentions UI uniquement · NOT_EXECUTED')).toBeInTheDocument();
});

test('NI1409 sequence takes external error and formatter, not browser threshold or channel values', async () => {
  const { client } = await loaded();
  fireEvent.click(screen.getByRole('tab', { name: 'Vide', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'NI1409', exact: true }));
  chooseCameraScenario('true', '44', 'driver source');
  fireEvent.change(screen.getByLabelText('Texte formaté caméra'), { target: { value: 'external text' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser séquence voie' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('camera_channel', {
    final_error: { status: true, code: 44, source: 'driver source' }, formatted_text: 'external text',
  }, expect.any(AbortSignal)));
  fireEvent.change(screen.getByLabelText('Texte formaté caméra'), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser séquence seuils' }));
  await waitFor(() => expect(client.replay).toHaveBeenLastCalledWith('camera_thresholds', {
    final_error: { status: true, code: 44, source: 'driver source' }, formatted_text: null,
  }, expect.any(AbortSignal)));
  expect(screen.getByText(/lectures locales LabVIEW non résolues/)).toBeInTheDocument();
});

test('density preview carries no invented NewVal or driver success', async () => {
  const { client } = await loaded();
  fireEvent.click(screen.getByRole('tab', { name: 'Vide', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier branche densité' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('video_density', {}, expect.any(AbortSignal)));
});

test.each([['pending', null, null], ['cancelled', true, null], ['selected', false, 'C:/opaque.tif']])(
  'TIFF %s produces typed dialog scenario, never a download or file write', async (dialog, cancelled, selected) => {
    const { client } = await loaded();
    fireEvent.click(screen.getByRole('tab', { name: 'Vide', exact: true }));
    fireEvent.click(screen.getByRole('tab', { name: 'TIFF', exact: true }));
    fireEvent.change(screen.getByLabelText('Année décodée TIFF'), { target: { value: '2026' } });
    fireEvent.change(screen.getByLabelText('Scénario dialogue TIFF'), { target: { value: dialog } });
    if (selected) fireEvent.change(screen.getByLabelText('Chemin TIFF fourni'), { target: { value: selected } });
    fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser TIFF' }));
    await waitFor(() => expect(client.replay).toHaveBeenCalledWith('save_image', {
      new_value: true, resolved_year: 2026, dialog_cancelled: cancelled, selected_path: selected,
    }, expect.any(AbortSignal)));
    expect(screen.getByText(/aucun dialogue système ni fichier écrit/)).toBeInTheDocument();
  });

test('TIFF preview rejects missing decoded year without defaulting to current date', async () => {
  const { client } = await loaded();
  fireEvent.click(screen.getByRole('tab', { name: 'Vide', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'TIFF', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser TIFF' }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('Entier I32 explicite requis'));
  expect(client.replay).not.toHaveBeenCalled();
});

function openBeamline(section) {
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'Diag', exact: true }));
  if (section && section !== 'Fentes') fireEvent.click(within(screen.getByRole('tablist', { name: 'Rejeu ligne faisceau' })).getByRole('tab', { name: section, exact: true }));
}

test('slit drafts call Python without copying formula or claiming calibrated mm/V', async () => {
  const { client } = await loaded();
  openBeamline();
  fireEvent.change(screen.getByLabelText('AXE H · brouillon'), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('GAP H · brouillon'), { target: { value: '10' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser positions fentes' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('slit_position', { axe_h: 2, gap_h: 10 }, expect.any(AbortSignal)));
  expect(screen.getByText('Simulation', { exact: true })).toBeInTheDocument();
});

test('blank slit value is unknown, never coerced to zero', async () => {
  const { client } = await loaded();
  openBeamline();
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser positions fentes' }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('Valeur numérique explicite requise'));
  expect(client.replay).not.toHaveBeenCalled();
});

test('slit supply selector zero remains integer zero, not a false pulse', async () => {
  const { client } = await loaded();
  openBeamline();
  fireEvent.change(screen.getByLabelText('Sélecteur alimentation fentes'), { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser alimentation fentes' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('slit_supply', { new_value: 0, frame_snapshots: null }, expect.any(AbortSignal)));
});

test('diagnostic station and selector use native server metadata without invented IN/OUT labels', async () => {
  const { client } = await loaded();
  openBeamline('T1–T3');
  fireEvent.change(screen.getByLabelText('Station diagnostique'), { target: { value: 'T3' } });
  fireEvent.change(screen.getByLabelText('Sélecteur position diagnostique'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser position diagnostique' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('diagnostic_position', { station: 'T3', selector: 2 }, expect.any(AbortSignal)));
});

test('Faraday NewVal must be supplied, and false remains a native empty branch', async () => {
  const client = clientFixture();
  client.replay.mockResolvedValue({ schema_version: 1, execution_allowed: false, physical_status: 'NOT_EXECUTED', operation: 'faraday_position',
    result: { frames: [], projection_origin: 'UNRESOLVED_LOCAL_READS' } });
  await loaded(client);
  openBeamline('Faraday');
  fireEvent.change(screen.getByLabelText('Station Faraday'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser événement Position Faraday' }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('inconnu ≠ false'));
  expect(client.replay).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('NewVal Position Faraday'), { target: { value: 'false' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser événement Position Faraday' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('faraday_position', { station: 2, new_value: false, frame_snapshots: null }, expect.any(AbortSignal)));
  expect(await screen.findByText('Branche vide : aucune écriture.')).toBeInTheDocument();
});

test('Faraday Arrêt requires every EN input and is not presented as hardware STOP', async () => {
  const { client } = await loaded();
  openBeamline('Faraday');
  fireEvent.change(screen.getByLabelText('Événement Faraday'), { target: { value: 'tab' } });
  fireEvent.change(screen.getByLabelText('Sélecteur onglet Faraday'), { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser onglet Faraday' }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('inconnu ≠ false'));
  expect(client.replay).not.toHaveBeenCalled();
  ['false', 'true', 'false'].forEach((value, i) => fireEvent.change(screen.getByLabelText(`Etat Faraday ${i + 1} EN · scénario`), { target: { value } }));
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser onglet Faraday' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('faraday_tab', { new_value: 0, en_states: [false, true, false], frame_snapshots: null }, expect.any(AbortSignal)));
  expect(screen.getByText('Simulation', { exact: true })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'STOP', exact: true })).not.toBeInTheDocument();
});

test('passive Faraday tab carries null EN rather than manufacturing False readback', async () => {
  const { client } = await loaded();
  openBeamline('Faraday');
  fireEvent.change(screen.getByLabelText('Événement Faraday'), { target: { value: 'tab' } });
  fireEvent.change(screen.getByLabelText('Sélecteur onglet Faraday'), { target: { value: '3' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser onglet Faraday' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('faraday_tab', { new_value: 3, en_states: null, frame_snapshots: null }, expect.any(AbortSignal)));
});

test('mirror forwards independent per-frame snapshots and does not chain them in the browser', async () => {
  const client = clientFixture();
  client.replay.mockResolvedValue({ schema_version: 1, execution_allowed: false, physical_status: 'NOT_EXECUTED', operation: 'laser_mirror',
    result: { frames: [{ index: 0, patches: [['native field', true]], waits_ms: [500], operations_within_frame_serialized: false }] } });
  await loaded(client);
  openBeamline('Miroir');
  fireEvent.change(screen.getByLabelText('Sélecteur miroir LASER'), { target: { value: '1' } });
  fireEvent.click(screen.getByText('Snapshots C5 par frame (facultatif)'));
  const snapshots = [{ frame_index: 0, cluster: { unrelated: false } }, { frame_index: 2, cluster: { unrelated: true } }];
  fireEvent.change(screen.getByLabelText('Snapshots C5 JSON'), { target: { value: JSON.stringify(snapshots) } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser miroir LASER' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('laser_mirror', { new_value: 1, frame_snapshots: snapshots }, expect.any(AbortSignal)));
  expect(await screen.findByText(/ordre intra-frame non prouvé/)).toBeInTheDocument();
});

test('invalid snapshot JSON rejects locally before any replay request', async () => {
  const { client } = await loaded();
  openBeamline('Miroir');
  fireEvent.change(screen.getByLabelText('Sélecteur miroir LASER'), { target: { value: '0' } });
  fireEvent.change(screen.getByLabelText('Snapshots C5 JSON'), { target: { value: '{' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser miroir LASER' }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('Rejeu refusé'));
  expect(client.replay).not.toHaveBeenCalled();
});

test('existing synchronisation JSON replay remains accessible inside Diag', async () => {
  await loaded();
  openBeamline('Synchronisation');
  expect(screen.getByLabelText('Entrées JSON · synchronisation')).toBeInTheDocument();
});

test('centroid RESET previews flag sequence without changing unknown coordinates', async () => {
  const client = clientFixture();
  client.replay.mockResolvedValue({ schema_version: 1, execution_allowed: false, physical_status: 'NOT_EXECUTED', operation: 'centroid_reset',
    result: { steps: [{ frame_index: 0, target: 'Init moy CxCy', value: true, observed_wait_ms: null },
      { frame_index: 1, target: null, value: null, observed_wait_ms: 200 }, { frame_index: 2, target: 'Init moy CxCy', value: false, observed_wait_ms: null }] } });
  await loaded(client);
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'Centroïde', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser RESET moy CxCy' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('centroid_reset', {}, expect.any(AbortSignal)));
  expect(await screen.findByText('Frame 1 : Wait 200 ms (intention)')).toBeInTheDocument();
  expect(screen.getByText('Centroïde X', { exact: true }).parentElement).toHaveTextContent('—');
  expect(screen.queryByRole('button', { name: 'STOP', exact: true })).not.toBeInTheDocument();
});

test('pending beamline replay disables snapshot edits and aborts on unmount', async () => {
  const client = clientFixture();
  let resolve;
  client.replay.mockImplementation(() => new Promise((done) => { resolve = done; }));
  const { unmount } = await loaded(client);
  openBeamline('Miroir');
  fireEvent.change(screen.getByLabelText('Sélecteur miroir LASER'), { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser miroir LASER' }));
  expect(screen.getByLabelText('Sélecteur miroir LASER')).toBeDisabled();
  expect(screen.getByLabelText('Snapshots C5 JSON')).toBeDisabled();
  const signal = client.replay.mock.calls[0][2];
  unmount();
  expect(signal.aborted).toBe(true);
  await act(async () => resolve({ result: {} }));
});

test.each([1, 2, 3, 4])('Translateurs selection %s sends only the typed selector', async (selection) => {
  const { client } = await loaded();
  openBeamline('Translateurs');
  fireEvent.change(screen.getByLabelText('Sélection Translateurs'), { target: { value: String(selection) } });
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser sélection Translateurs' }));
  await waitFor(() => expect(client.replay).toHaveBeenCalledWith('translator_selection', { selection }, expect.any(AbortSignal)));
  expect(screen.getByText('Simulation', { exact: true })).toBeInTheDocument();
});

test('Translateurs selector remains unresolved until supplied', async () => {
  const { client } = await loaded();
  openBeamline('Translateurs');
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser sélection Translateurs' }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('Choisir explicitement'));
  expect(client.replay).not.toHaveBeenCalled();
});

test('Translateurs Arrêt renders topology and unknown destination without pretending a safe stop', async () => {
  const client = clientFixture();
  client.replay.mockResolvedValue({ schema_version: 1, execution_allowed: false, operation: 'translator_stop', result: { frames: [
    { index: 1, topology: ['native frame topology'], shared_variable_write: { psp_url: null, assignments: [{ field: 'native screen', value: 2.126 }] } },
    { index: 2, topology: ['polling topology'], polling_selector: { expression: 'raw Boolean' } },
  ] } });
  await loaded(client);
  openBeamline('Translateurs');
  fireEvent.change(screen.getByLabelText('Modèle Translateurs'), { target: { value: 'stop' } });
  fireEvent.click(screen.getByRole('button', { name: 'Inspecter graphe Arrêt Translateurs' }));
  await screen.findByText('Destination PSP non capturée · écriture bloquée');
  expect(client.replay).toHaveBeenCalledWith('translator_stop', {}, expect.any(AbortSignal));
  expect(screen.getByText(/graphe statique UNMAPPED ; aucun état sûr/)).toBeInTheDocument();
  expect(screen.getByText(/native screen = 2.126/)).toBeInTheDocument();
});

test('raw polling result is not rendered as a stop decision', async () => {
  const client = clientFixture();
  client.replay.mockResolvedValue({ schema_version: 1, execution_allowed: false, operation: 'translator_loop_selector', result: { expression_value: false, termination_semantics: 'NATIVE_UNVERIFIED' } });
  await loaded(client);
  openBeamline('Translateurs');
  fireEvent.change(screen.getByLabelText('Modèle Translateurs'), { target: { value: 'expression' } });
  for (const [label, value] of [['Itération boucle · scénario', '1200'], ['Position Miroir Laser · scénario', '22.7'], ['Etat T1 · scénario', '22.7'], ['Etat MLaser EN · scénario', '22.7']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer expression Translateurs' }));
  expect(await screen.findByText(/Expression brute = false/)).toHaveTextContent('pas de décision d’arrêt');
  expect(client.replay).toHaveBeenCalledWith('translator_loop_selector', { iteration: 1200, position_miroir_laser: 22.7, etat_t1: 22.7, etat_mlaser_en: 22.7 }, expect.any(AbortSignal));
});

test('blank polling measurements are not coerced to zero', async () => {
  const { client } = await loaded();
  openBeamline('Translateurs');
  fireEvent.change(screen.getByLabelText('Modèle Translateurs'), { target: { value: 'expression' } });
  fireEvent.change(screen.getByLabelText('Itération boucle · scénario'), { target: { value: '1201' } });
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer expression Translateurs' }));
  await waitFor(() => expect(screen.getByRole('status', { name: 'État du rejeu SuperVision' })).toHaveTextContent('Valeur numérique explicite requise'));
  expect(client.replay).not.toHaveBeenCalled();
});

test('Vidéo connects motor replay to the Python backend and shows no actual position', async () => {
  const client = clientFixture();
  client.replay.mockResolvedValue({ schema_version: 1, execution_allowed: false, operation: 'motor_jog', result: {
    control_label: 'Move reverse X', motor_number: 3, signed_steps: -10,
    motion_call: { operation: 'RelativeMove.vi' }, polling_calls: [{ operation: 'GetPosition.vi' }],
  } });
  await loaded(client);
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'Vidéo', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'X/Y', exact: true }));
  for (const [label, value] of [['Contrôle déplacement natif', 'Move reverse X'], ['Relative Steps · I32', '10'], ['Numéro moteur X · U32', '3'], ['Numéro moteur Y · U32', '4']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser déplacement X/Y' }));
  expect(await screen.findByText(/pas signés = -10/)).toHaveTextContent('aucune position physique');
  expect(client.replay).toHaveBeenCalledWith('motor_jog', { control_label: 'Move reverse X', motor_numbers: [3, 4], relative_steps: 10 }, expect.any(AbortSignal));
});

test('autotune shows simultaneous GoTo intent and termination without claiming direction or success', async () => {
  const client = clientFixture();
  client.replay.mockResolvedValue({ schema_version: 1, execution_allowed: false, operation: 'autotune_iteration', result: {
    in_band: false, terminate_inner_loop: true, wait_ms: 3000,
    move_intent: { arguments: [['Relative Steps', 10], ['true_connector_index', 2]] },
  } });
  await loaded(client);
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'Vidéo', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'Autotune', exact: true }));
  for (const [label, value] of [['Étape autotune', 'CHANNEL3_X'], ['Coordonnée centroïde · scénario', '252'], ['stop motor · scénario', 'true'], ['Erreur moteur autotune · scénario', 'true']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer itération autotune' }));
  expect(await screen.findByText(/GoTo \(intention\)/)).toHaveTextContent('direction non déduite');
  expect(screen.getByText(/sortie boucle interne = true/)).toBeInTheDocument();
  expect(screen.getByText('stop/erreur ne constitue pas une garde avant GoTo.')).toBeInTheDocument();
});

test('pending motor replay is aborted on unmount without invoking a hardware stop', async () => {
  const client = clientFixture();
  client.replay.mockImplementation(() => new Promise(() => {}));
  const { unmount } = await loaded(client);
  fireEvent.click(screen.getByRole('tab', { name: 'Contrôle / Diagnostics / FISO', exact: true }));
  fireEvent.click(screen.getByRole('tab', { name: 'Vidéo', exact: true }));
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser initialisation moteurs' }));
  await waitFor(() => expect(screen.getByLabelText('Clé découverte fournie')).toBeDisabled());
  const signal = client.replay.mock.calls[0][2];
  unmount();
  expect(signal.aborted).toBe(true);
  expect(client.replay).toHaveBeenCalledTimes(1);
});
