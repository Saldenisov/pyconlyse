import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import SupervisionDiagnostics from './SupervisionDiagnostics';

const SOURCE = 'a'.repeat(32);
const CAPTURE = 'c'.repeat(32);
const id = 'ni1409:2';
function camera(overrides = {}) {
  return { camera_id: id, channel: 2, source_session_id: SOURCE, capture_session_id: CAPTURE,
    sequence: 1, width: 4, height: 3, frame_identity: `${SOURCE}/${CAPTURE}/1/2`,
    source_kind: 'python_supervision_ni1409', processing: 'raw_grab_before_legacy_interlace_bcg_profiles',
    current: { x: 1, y: 1.5, valid: true, age_seconds: .1, quality: 'CURRENT', reason: '' },
    profiles: { x: [0, 10, 20, 0], y: [0, 30, 0] }, reference: null, mode: 'manual', mode_revision: 0,
    planner: { execution_allowed: false, state: 'UNCOMMISSIONED', reason: 'Calibration moteur non raccordée.' },
    manual: { enabled: false, reason: 'Route picomoteur non raccordée.' }, ...overrides };
}
function video(channel = 2, sequence = 1) {
  const frame = { source: 'python_supervision_ni1409', simulated: false, sequence,
    sequence_interpretation: 'software grab observation, not hardware frame counter',
    capture_session_id: CAPTURE, observed_utc: '2026-10-29T08:00:00+00:00',
    sample_elapsed_seconds: .01, source_age_seconds: .1, width: 4, height: 3,
    pixel_type: 'U8', encoding: 'base64_raw_row_major', data: 'AAECAwQFBgcICQoL', channel,
    processing: 'raw_grab_before_legacy_interlace_bcg_profiles', hardware_acknowledged: false };
  const { data, sample_elapsed_seconds, source_age_seconds, sequence_interpretation, simulated, ...metadata } = frame;
  return { schema_version: 1, owner: 'supervision', available: true, stale: false,
    session_id: SOURCE, age_seconds: .1, source_mode: 'PYTHON_NATIVE', ...metadata, frame };
}
const envelope = (row = camera()) => ({ schema_version: 1, cameras: [row], execution_allowed: false, hardware_writes: false });
let context;
beforeEach(() => {
  jest.useFakeTimers();
  context = { createImageData: jest.fn((width, height) => ({ data: new Uint8ClampedArray(width * height * 4) })),
    putImageData: jest.fn() };
  jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context);
});
afterEach(() => { jest.restoreAllMocks(); jest.useRealTimers(); });
const flush = async () => { await act(async () => { await Promise.resolve(); }); };
const advance = async (ms) => { await act(async () => { jest.advanceTimersByTime(ms); }); };
function mount(row = camera()) {
  const client = { snapshot: jest.fn().mockResolvedValue(envelope(row)), saveReference: jest.fn(), setMode: jest.fn() };
  const videoClient = { video: jest.fn().mockResolvedValue(video()) };
  const result = render(<SupervisionDiagnostics client={client} videoClient={videoClient} />);
  return { client, videoClient, ...result };
}

test('native hierarchy preserves three independent Diag subtab groups without actuator dispatch', async () => {
  const { client, unmount } = mount();
  await flush();
  const tabs = screen.getByRole('tablist', { name: 'Onglets diagnostics SuperVision' });
  expect(within(tabs).getAllByRole('tab').map((button) => button.textContent))
    .toEqual(['Centroïde', 'Profils X Y', 'Diag', 'WCM', 'Beam profile']);
  fireEvent.click(within(tabs).getByRole('tab', { name: 'Diag', exact: true }));
  const laser = screen.getByRole('region', { name: 'Laser / translateurs' });
  const faraday = screen.getByRole('region', { name: 'Cages de Faraday' });
  const slit = screen.getByRole('region', { name: 'Fente', exact: true });
  fireEvent.click(within(laser).getByRole('tab', { name: 'Laser', exact: true }));
  fireEvent.click(within(faraday).getByRole('tab', { name: 'Cage Faraday3' }));
  fireEvent.click(within(slit).getByRole('tab', { name: 'Fente' }));
  expect(within(laser).getByRole('tab', { name: 'Laser', exact: true })).toHaveAttribute('aria-selected', 'true');
  expect(within(faraday).getByRole('tab', { name: 'Cage Faraday3' })).toHaveAttribute('aria-selected', 'true');
  expect(within(slit).getByRole('tab', { name: 'Fente' })).toHaveAttribute('aria-selected', 'true');
  expect(within(laser).getByRole('combobox', { name: 'Position Miroir Laser' })).toBeDisabled();
  expect(within(laser).getByLabelText('Etat MLaser EN')).toHaveTextContent('Inconnu');
  expect(within(faraday).getByRole('combobox', { name: 'Position Faraday 3' })).toBeDisabled();
  expect(within(slit).getByRole('spinbutton', { name: 'AXE H' })).toBeDisabled();
  expect(client.saveReference).not.toHaveBeenCalled();
  expect(client.setMode).not.toHaveBeenCalled();
  unmount();
});

test.each([
  [1, 28485, 28471, 28052], [2, 29402, 33032, 38266], [3, 30891, 30875, 25389],
])('Translateur%s presents exact native position/command/readback controls without manufactured values',
  async (station, position, command, readback) => {
    const { client, unmount } = mount();
    await flush();
    fireEvent.click(within(screen.getByRole('tablist', { name: 'Onglets diagnostics SuperVision' }))
      .getByRole('tab', { name: 'Diag', exact: true }));
    const group = screen.getByRole('region', { name: 'Laser / translateurs' });
    fireEvent.click(within(group).getByRole('tab', { name: `Translateur${station}` }));
    const control = within(group).getByRole('combobox', { name: `Position diagnostique T${station}` });
    expect(control).toBeDisabled();
    expect(control.closest('[data-native-id]')).toHaveAttribute('data-native-id', String(position));
    expect(within(control).getAllByRole('option').map((option) => option.textContent))
      .toEqual(['Non lu', 'Position FAISCEAU', 'Position ECRAN', 'Position CERENKOV']);
    const setpoint = within(group).getByRole('spinbutton', { name: `Cmd pos T${station}` });
    expect(setpoint).toBeDisabled();
    expect(setpoint).toHaveValue(null);
    expect(setpoint.closest('[data-native-id]')).toHaveAttribute('data-native-id', String(command));
    const reading = within(group).getByLabelText(`Lec. pos T${station}`);
    expect(reading).toHaveTextContent('—');
    expect(reading.closest('[data-native-id]')).toHaveAttribute('data-native-id', String(readback));
    expect(within(group).getByLabelText(`Etat T${station}`)).toHaveTextContent('Inconnu');
    expect(client.setMode).not.toHaveBeenCalled();
    expect(client.saveReference).not.toHaveBeenCalled();
    unmount();
  });

test('Faraday EN/HORS and native horizontal slit setpoints stay distinct from unknown readbacks', async () => {
  const { client, unmount } = mount();
  await flush();
  fireEvent.click(within(screen.getByRole('tablist', { name: 'Onglets diagnostics SuperVision' }))
    .getByRole('tab', { name: 'Diag', exact: true }));
  const faraday = screen.getByRole('region', { name: 'Cages de Faraday' });
  fireEvent.click(within(faraday).getByRole('tab', { name: 'Cage Faraday1' }));
  expect(within(faraday).getByLabelText('Etat Faraday 1 EN')).toHaveTextContent('Inconnu');
  expect(within(faraday).getByLabelText('Etat Faraday 1 HORS')).toHaveTextContent('Inconnu');
  expect(within(faraday).getByRole('combobox', { name: 'Position Faraday 1' })).toBeDisabled();
  const slit = screen.getByRole('region', { name: 'Fente', exact: true });
  fireEvent.click(within(slit).getByRole('tab', { name: 'Fente' }));
  expect(within(slit).getByRole('spinbutton', { name: 'AXE H' })).toBeDisabled();
  expect(within(slit).getByRole('spinbutton', { name: 'GAP H' })).toBeDisabled();
  for (const label of ['AXE FENTE H', 'GAP FENTE H', 'AXE FENTE V', 'GAP FENTE V']) {
    expect(within(slit).getByLabelText(label)).toHaveTextContent('—');
  }
  expect(within(slit).queryByRole('spinbutton', { name: 'AXE V' })).not.toBeInTheDocument();
  expect(client.setMode).not.toHaveBeenCalled();
  expect(client.saveReference).not.toHaveBeenCalled();
  unmount();
});

test('save-center below image sends observed frame identity and latest reference revision, never clicked coordinates', async () => {
  const { client, unmount } = mount();
  await flush();
  const saved = { x: 1, y: 1.5, radius_px: 10, width: 4, height: 3, revision: 1, saved_utc: '2026-10-29T08:00:00+00:00',
    source_kind: 'python_supervision_ni1409', processing: 'raw_grab_before_legacy_interlace_bcg_profiles' };
  client.saveReference.mockResolvedValue(envelope(camera({ reference: saved })));
  const button = screen.getByRole('button', { name: 'Enregistrer le centre' });
  expect(button).toBeEnabled();
  expect(screen.getByRole('img', { name: 'Dernière image Canal brut 2 · NI1409' })
    .compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  fireEvent.click(button);
  await flush();
  expect(client.saveReference).toHaveBeenCalledWith({ camera_id: id,
    frame_identity: `${SOURCE}/${CAPTURE}/1/2`, expected_revision: 0, radius_px: 10 }, expect.any(AbortSignal));
  expect(screen.getByTestId('reference-cross')).toBeInTheDocument();
  expect(screen.getByTestId('current-centroid')).toHaveAttribute('cx', '1');
  expect(screen.getByTestId('reference-tolerance')).toHaveAttribute('data-inside', 'true');
  await advance(250); // Old periodic response cannot replace a newly saved revision.
  expect(screen.getByText(/révision 1/)).toBeInTheDocument();
  unmount();
});

test('auto preference saves mode only and leaves uncommissioned physical correction explicit', async () => {
  const { client, unmount } = mount();
  await flush();
  client.setMode.mockResolvedValue(envelope(camera({ mode: 'auto', mode_revision: 1 })));
  fireEvent.click(screen.getByRole('button', { name: 'Auto', exact: true }));
  await flush();
  expect(client.setMode).toHaveBeenCalledWith({ camera_id: id, mode: 'auto', expected_revision: 0 }, expect.any(AbortSignal));
  expect(screen.getByRole('button', { name: 'Auto', exact: true })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('status', { name: 'État du centrage automatique' })).toHaveTextContent('UNCOMMISSIONED');
  expect(screen.getByRole('button', { name: 'X avant' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Arrêt moteur' })).toBeDisabled();
  expect(client.saveReference).not.toHaveBeenCalled();
  unmount();
});

test('stale or mismatched image does not show a live point or allow saving while reference stays', async () => {
  const saved = { x: 1, y: 1, width: 4, height: 3, radius_px: 2, revision: 4,
    source_kind: 'python_supervision_ni1409', processing: 'raw_grab_before_legacy_interlace_bcg_profiles' };
  const { videoClient, unmount } = mount(camera({ reference: saved }));
  await flush();
  const canvas = screen.getByRole('img', { name: 'Dernière image Canal brut 2 · NI1409' });
  expect(screen.getByTestId('current-centroid')).toBeInTheDocument();
  videoClient.video.mockResolvedValue(video(2, 2));
  await advance(40);
  expect(screen.getByRole('img', { name: 'Dernière image Canal brut 2 · NI1409' })).toBe(canvas);
  expect(screen.queryByTestId('current-centroid')).not.toBeInTheDocument();
  expect(screen.getByTestId('reference-cross')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Enregistrer le centre' })).toBeDisabled();
  await advance(2200);
  expect(screen.queryByTestId('current-centroid')).not.toBeInTheDocument();
  expect(screen.getByRole('img', { name: 'Dernière image Canal brut 2 · NI1409' })).toBe(canvas);
  unmount();
});

test('two-view selection cannot relabel one channel as a second live camera', async () => {
  const { videoClient, unmount } = mount();
  await flush();
  videoClient.video.mockImplementation((signal, { channel }) => Promise.resolve(channel === 2 ? video(2)
    : { schema_version: 1, owner: 'supervision', available: false, stale: true, frame: null }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Deux vues indépendantes' }));
  await flush();
  expect(screen.getAllByRole('img', { name: /Dernière image/ })).toHaveLength(1);
  expect(screen.getByRole('region', { name: 'Canal brut 1 · NI1409' })).toHaveTextContent('Vidéo indisponible');
  expect(screen.getByRole('region', { name: 'Canal brut 2 · NI1409' })).toHaveTextContent('Image récente');
  expect(videoClient.video.mock.calls.some(([, options]) => options.channel === 1)).toBe(true);
  unmount();
});

test('profiles show measured axes and missing measurement remains unavailable', async () => {
  const { client, unmount } = mount();
  await flush();
  fireEvent.click(screen.getByRole('tab', { name: 'Profils X Y' }));
  expect(screen.getByText('4 pixels · maximum 20.0')).toBeInTheDocument();
  expect(screen.getByText('3 pixels · maximum 30.0')).toBeInTheDocument();
  client.snapshot.mockResolvedValue(envelope(camera({ current: { valid: false, quality: 'NO_BEAM' } })));
  await advance(250);
  expect(screen.getAllByText('Profil actuel indisponible.')).toHaveLength(2);
  unmount();
});

test('persistence rejection is visible and does not create a reference marker', async () => {
  const { client, unmount } = mount();
  await flush();
  client.saveReference.mockRejectedValue(new Error('PostgreSQL indisponible : centre non enregistré.'));
  fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le centre' }));
  await flush();
  expect(screen.getByRole('alert')).toHaveTextContent('centre non enregistré');
  expect(screen.queryByTestId('reference-cross')).not.toBeInTheDocument();
  unmount();
});
