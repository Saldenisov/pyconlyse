import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ElyseMotion from './ElyseMotion';

const META = {
  jog_labels: ['Move forward X', 'Move forward Y', 'Move reverse X', 'Move reverse Y'],
  jog_event_indices: [28, 29], error_event_indices: [27, 28, 29],
  autotune_stages: ['CHANNEL3_X', 'CHANNEL3_Y', 'CHANNEL2_X', 'CHANNEL2_Y'],
  autotune_channels: [2, 3],
};
function fixture(overrides = {}) {
  const errors = [];
  const context = { snapshot: { motion_controls: META }, pending: false, run: jest.fn().mockResolvedValue({}),
    attempt: jest.fn((callback) => Promise.resolve().then(callback).catch((e) => errors.push(e.message))), ...overrides };
  return { context, errors, ...render(<ElyseMotion context={context} />) };
}
function open(section) {
  fireEvent.click(screen.getByRole('tab', { name: section, exact: true }));
}
function change(label, value) {
  fireEvent.change(screen.getByLabelText(label, { exact: true }), { target: { value } });
}
function errorScenario(status = 'false', code = '0', source = '') {
  change('Statut erreur externe moteur/caméra', status);
  change('Code erreur externe moteur/caméra (I32)', code);
  change('Source erreur externe moteur/caméra', source);
}

test.each([null, '', 'external-key'])('initialization keeps discovery %s distinct', async (key) => {
  const { context } = fixture();
  if (key !== null) {
    fireEvent.click(screen.getByLabelText('Clé découverte fournie'));
    change('Clé découverte', key);
  }
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser initialisation moteurs' }));
  await waitFor(() => expect(context.run).toHaveBeenCalledWith('motor_initialization', { discovered_key: key }));
  expect(screen.getByText(/SetZeroPosition/)).toHaveTextContent('intentions seulement');
});

test.each(META.jog_labels)('jog %s sends typed input, never computes motion in JS', async (label) => {
  const { context } = fixture();
  open('X/Y');
  change('Contrôle déplacement natif', label);
  change('Relative Steps · I32', '-10');
  change('Numéro moteur X · U32', '3');
  change('Numéro moteur Y · U32', '4');
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser déplacement X/Y' }));
  await waitFor(() => expect(context.run).toHaveBeenCalledWith('motor_jog', { control_label: label, motor_numbers: [3, 4], relative_steps: -10 }));
});

test('blank motor numbers remain unresolved instead of defaulting to zero', async () => {
  const { context, errors } = fixture();
  open('X/Y');
  change('Contrôle déplacement natif', 'Move forward X');
  change('Relative Steps · I32', '5');
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser déplacement X/Y' }));
  await waitFor(() => expect(errors).toEqual(['Entier externe explicite hors contrat I32/U32.']));
  expect(context.run).not.toHaveBeenCalled();
});

test.each(['false', 'true'])('polling error %s sends exact externally supplied values', async (status) => {
  const { context } = fixture();
  open('Polling');
  change('Événement polling moteur', '29');
  change('GetPosition · résultat I32', '-123');
  change('GetMotionDone · scénario', 'false');
  change('stop motor · scénario', 'true');
  errorScenario(status, '44', 'external');
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer polling moteur' }));
  await waitFor(() => expect(context.run).toHaveBeenCalledWith('motor_jog_poll', { event_index: 29, motion_done: false, stop_motor: true,
    motion_done_error: { status: status === 'true', code: 44, source: 'external' }, position_result: -123 }));
  expect(screen.getByText(/GetPosition non gardé/)).toBeInTheDocument();
});

test('polling does not manufacture a successful driver error cluster', async () => {
  const { context, errors } = fixture();
  open('Polling');
  change('Événement polling moteur', '28');
  change('GetPosition · résultat I32', '1');
  change('GetMotionDone · scénario', 'false');
  change('stop motor · scénario', 'false');
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer polling moteur' }));
  await waitFor(() => expect(errors[0]).toMatch('Booléen externe explicite requis'));
  expect(context.run).not.toHaveBeenCalled();
});

test.each(META.autotune_stages)('autotune %s forwards coordinate and stop/error without a browser pre-move guard', async (stage) => {
  const { context } = fixture();
  open('Autotune');
  change('Étape autotune', stage);
  change('Coordonnée centroïde · scénario', '252');
  change('stop motor · scénario', 'true');
  change('Erreur moteur autotune · scénario', 'true');
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer itération autotune' }));
  await waitFor(() => expect(context.run).toHaveBeenCalledWith('autotune_iteration', { stage, coordinate: 252, stop_motor: true, motor_error: true }));
  expect(screen.getByText(/intention GoTo possible même avec stop\/erreur/)).toBeInTheDocument();
});

test('autotune blank coordinate is not a measured zero', async () => {
  const { context, errors } = fixture();
  open('Autotune');
  change('Étape autotune', 'CHANNEL2_X');
  change('stop motor · scénario', 'false');
  change('Erreur moteur autotune · scénario', 'false');
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer itération autotune' }));
  await waitFor(() => expect(errors[0]).toMatch('Coordonnée externe finie requise'));
  expect(context.run).not.toHaveBeenCalled();
});

test('outer autotune sends only Y flags and stop, not invented X success or motor error', async () => {
  const { context } = fixture();
  open('Autotune');
  change('Modèle autotune', 'outer');
  change('Caméra 3 Y dans bande · scénario', 'true');
  change('Caméra 2 Y dans bande · scénario', 'false');
  change('stop motor · scénario', 'false');
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer boucle externe autotune' }));
  await waitFor(() => expect(context.run).toHaveBeenCalledWith('autotune_outer', { channel3_y_in_band: true, channel2_y_in_band: false, stop_motor: false }));
  expect(screen.getByText(/ignore la convergence X et l’erreur moteur/)).toBeInTheDocument();
});

test('outer autotune does not convert unknown booleans to false', async () => {
  const { context, errors } = fixture();
  open('Autotune');
  change('Modèle autotune', 'outer');
  fireEvent.click(screen.getByRole('button', { name: 'Évaluer boucle externe autotune' }));
  await waitFor(() => expect(errors[0]).toMatch('Booléen externe explicite requis'));
  expect(context.run).not.toHaveBeenCalled();
});

test('global autotune plan is an inspection, not an execution or success action', async () => {
  const { context } = fixture();
  open('Autotune');
  change('Modèle autotune', 'plan');
  fireEvent.click(screen.getByRole('button', { name: 'Inspecter plan autotune' }));
  await waitFor(() => expect(context.run).toHaveBeenCalledWith('autotune_plan', {}));
  expect(screen.getByText(/sans garde de réussite/)).toBeInTheDocument();
});

test.each([[2, false], [2, true], [3, false], [3, true]])('camera autotune %s error=%s sends separate typed native camera plan', async (channel, status) => {
  const { context } = fixture();
  open('Caméra');
  change('Voie caméra autotune', String(channel));
  errorScenario(String(status), '42', 'camera');
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser caméra autotune' }));
  await waitFor(() => expect(context.run).toHaveBeenCalledWith('autotune_camera', { channel, final_error: { status, code: 42, source: 'camera' } }));
  expect(screen.getByText(/8 frames/)).toBeInTheDocument();
});

test('motor error journal remains a separate blocked file intent', async () => {
  const { context } = fixture();
  open('Erreurs');
  change('Événement journal moteur', '27');
  errorScenario('true', '-1', 'source');
  fireEvent.click(screen.getByRole('button', { name: 'Prévisualiser journal erreur moteur' }));
  await waitFor(() => expect(context.run).toHaveBeenCalledWith('motor_error', { event_index: 27, final_error: { status: true, code: -1, source: 'source' } }));
  expect(screen.getByText('Aucun fichier Erreurs.xls créé ou écrit.')).toBeInTheDocument();
});

test('missing motion metadata disables model inputs and preview buttons', () => {
  fixture({ snapshot: {} });
  expect(screen.getByLabelText('Clé découverte fournie')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Prévisualiser initialisation moteurs' })).toBeDisabled();
});

test('pending replay disables inputs across tabs; no STOP command is introduced', () => {
  fixture({ pending: true });
  open('Autotune');
  expect(screen.getByLabelText('Étape autotune')).toBeDisabled();
  expect(screen.getByLabelText('stop motor · scénario')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Évaluer itération autotune' })).toBeDisabled();
  expect(screen.queryByRole('button', { name: 'STOP', exact: true })).not.toBeInTheDocument();
});
