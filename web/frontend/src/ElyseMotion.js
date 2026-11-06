import React, { useState } from 'react';
import useElyseUiState from './useElyseUiState';

const SECTIONS = ['Initialisation', 'X/Y', 'Polling', 'Autotune', 'Caméra', 'Erreurs'];
const BOOLEANS = [['false', 'false · scénario'], ['true', 'true · scénario']];
function Choice({ label, value, change, options, disabled }) {
  return <label>{label}<select aria-label={label} value={value} disabled={disabled} onChange={(e) => change(e.target.value)}>
    <option value="">Choisir…</option>{options.map((item) => {
      const [key, text] = Array.isArray(item) ? item : [item, String(item)];
      return <option key={key} value={String(key)}>{text}</option>;
    })}</select></label>;
}
function explicitBoolean(value) {
  if (!['false', 'true'].includes(value)) throw new Error('Booléen externe explicite requis ; inconnu ≠ false.');
  return value === 'true';
}
function integer(value, min = -(2 ** 31), max = 2 ** 31 - 1) {
  const n = Number(value);
  if (!/^-?\d+$/.test(value) || !Number.isSafeInteger(n) || n < min || n > max) throw new Error('Entier externe explicite hors contrat I32/U32.');
  return n;
}
function real(value) {
  if (!value.trim() || !Number.isFinite(Number(value))) throw new Error('Coordonnée externe finie requise ; aucun centroïde mesuré.');
  return Number(value);
}

export default function ElyseMotion({ context }) {
  const [section, setSection] = useElyseUiState('elyse.supervision.motion.tab', 'Initialisation', SECTIONS, context.persistUi === true);
  const [keyResolved, setKeyResolved] = useState(false);
  const [key, setKey] = useState('');
  const [jogLabel, setJogLabel] = useState('');
  const [motors, setMotors] = useState(['', '']);
  const [steps, setSteps] = useState('');
  const [pollEvent, setPollEvent] = useState('');
  const [done, setDone] = useState('');
  const [stop, setStop] = useState('');
  const [position, setPosition] = useState('');
  const [errorStatus, setErrorStatus] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [errorSource, setErrorSource] = useState('');
  const [errorEvent, setErrorEvent] = useState('');
  const [autotuneMode, setAutotuneMode] = useState('iteration');
  const [stage, setStage] = useState('');
  const [coordinate, setCoordinate] = useState('');
  const [motorError, setMotorError] = useState('');
  const [yBands, setYBands] = useState(['', '']);
  const [channel, setChannel] = useState('');
  const meta = context.snapshot?.motion_controls;
  const disabled = context.pending || !meta;
  const numberInput = (label, value, change, step = '1') => <label>{label}<input type="number" step={step} aria-label={label} value={value} disabled={disabled} onChange={(e) => change(e.target.value)} /></label>;
  const bool = (label, value, change) => <Choice label={label} value={value} change={change} options={BOOLEANS} disabled={disabled} />;
  const errorScenario = () => ({ status: explicitBoolean(errorStatus), code: integer(errorCode), source: errorSource });
  const errorInputs = <>
    {bool('Statut erreur externe moteur/caméra', errorStatus, setErrorStatus)}
    {numberInput('Code erreur externe moteur/caméra (I32)', errorCode, setErrorCode)}
    <label className="elyse-motion-wide">Source erreur externe moteur/caméra<input aria-label="Source erreur externe moteur/caméra" value={errorSource} disabled={disabled} onChange={(e) => setErrorSource(e.target.value)} /></label>
  </>;
  const button = (label, operation, inputs) => <button type="button" className="elyse-hardware-button" disabled={disabled}
    onClick={() => context.attempt(() => context.run(operation, inputs()))}>{label}</button>;
  return <div className="elyse-motion">
    <div className="elyse-subtabs" role="tablist" aria-label="Rejeu moteurs et autotune">{SECTIONS.map((name) =>
      <button type="button" role="tab" key={name} aria-selected={section === name} className={section === name ? 'is-active' : ''} onClick={() => setSection(name)}>{name}</button>)}</div>
    <p className="elyse-replay-note">Scénarios externes · aucune découverte, position mesurée, remise à zéro ou action moteur/caméra.</p>
    {section === 'Initialisation' && <>
      <div className="elyse-motion-grid">
        <label className="elyse-motion-wide"><span><input type="checkbox" aria-label="Clé découverte fournie" checked={keyResolved} disabled={disabled} onChange={(e) => setKeyResolved(e.target.checked)} />Clé découverte fournie (vide ≠ inconnue)</span>
          <input aria-label="Clé découverte" value={key} disabled={disabled || !keyResolved} onChange={(e) => setKey(e.target.value)} /></label>
        {button('Prévisualiser initialisation moteurs', 'motor_initialization', () => ({ discovered_key: keyResolved ? key : null }))}
      </div>
      <small>Clé non vide : identification puis SetZeroPosition(1…4), intentions seulement. Ni adresse ni réussite pilote établies.</small>
    </>}
    {section === 'X/Y' && <>
      <div className="elyse-motion-grid">
        <Choice label="Contrôle déplacement natif" value={jogLabel} change={setJogLabel} options={meta?.jog_labels || []} disabled={disabled} />
        {numberInput('Relative Steps · I32', steps, setSteps)}
        {['X', 'Y'].map((axis, i) => <React.Fragment key={axis}>{numberInput(`Numéro moteur ${axis} · U32`, motors[i], (v) => setMotors((prev) => prev.map((n, j) => j === i ? v : n)))}</React.Fragment>)}
        {button('Prévisualiser déplacement X/Y', 'motor_jog', () => {
          if (!jogLabel) throw new Error('Choisir le contrôle natif X/Y ; aucune branche Default devinée.');
          return { control_label: jogLabel, motor_numbers: motors.map((n) => integer(n, 0, 2 ** 32 - 1)), relative_steps: integer(steps) };
        })}
      </div>
      <small>Reverse nie Relative Steps ; aucune garde NewVal ni timeout dans le modèle. Unités / limites physiques inconnues.</small>
    </>}
    {section === 'Polling' && <>
      <div className="elyse-motion-grid">
        <Choice label="Événement polling moteur" value={pollEvent} change={setPollEvent} options={meta?.jog_event_indices || []} disabled={disabled} />
        {numberInput('GetPosition · résultat I32', position, setPosition)}
        {bool('GetMotionDone · scénario', done, setDone)}
        {bool('stop motor · scénario', stop, setStop)}
        {errorInputs}
        {button('Évaluer polling moteur', 'motor_jog_poll', () => ({ event_index: integer(pollEvent), motion_done: explicitBoolean(done), motion_done_error: errorScenario(),
          stop_motor: explicitBoolean(stop), position_result: integer(position) }))}
      </div>
      <small>Sortie = done OU erreur GetMotionDone OU stop. Résultat GetPosition non gardé ; AbortMotion seulement comme intention.</small>
    </>}
    {section === 'Autotune' && <>
      <Choice label="Modèle autotune" value={autotuneMode} change={setAutotuneMode} options={[[ 'iteration', 'Une itération native'], ['outer', 'Condition boucle externe'], ['plan', 'Ordre global statique']]} disabled={disabled} />
      {autotuneMode === 'plan' && <>
        <p>Caméra 3 → X → Y → caméra 2 → X → Y. Message « Autotune terminé » sans garde de réussite.</p>
        {button('Inspecter plan autotune', 'autotune_plan', () => ({}))}
      </>}
      {autotuneMode === 'iteration' && <>
        <div className="elyse-motion-grid">
          <Choice label="Étape autotune" value={stage} change={setStage} options={meta?.autotune_stages || []} disabled={disabled} />
          {numberInput('Coordonnée centroïde · scénario', coordinate, setCoordinate, 'any')}
          {bool('stop motor · scénario', stop, setStop)}
          {bool('Erreur moteur autotune · scénario', motorError, setMotorError)}
          {button('Évaluer itération autotune', 'autotune_iteration', () => ({ stage, coordinate: real(coordinate), stop_motor: explicitBoolean(stop), motor_error: explicitBoolean(motorError) }))}
        </div>
        <small>Bande [249,251]. Hors bande, intention GoTo possible même avec stop/erreur. Wait 3000 ms ; fraîcheur non prouvée, aucun maximum d’itérations.</small>
      </>}
      {autotuneMode === 'outer' && <>
        <div className="elyse-motion-grid">
          {[3, 2].map((n, i) => <React.Fragment key={n}>{bool(`Caméra ${n} Y dans bande · scénario`, yBands[i], (v) => setYBands((prev) => prev.map((b, j) => j === i ? v : b)))}</React.Fragment>)}
          {bool('stop motor · scénario', stop, setStop)}
          {button('Évaluer boucle externe autotune', 'autotune_outer', () => ({ channel3_y_in_band: explicitBoolean(yBands[0]), channel2_y_in_band: explicitBoolean(yBands[1]), stop_motor: explicitBoolean(stop) }))}
        </div>
        <small>La condition native ignore la convergence X et l’erreur moteur. Pas de preuve d’alignement.</small>
      </>}
    </>}
    {section === 'Caméra' && <>
      <div className="elyse-motion-grid">
        <Choice label="Voie caméra autotune" value={channel} change={setChannel} options={meta?.autotune_channels || []} disabled={disabled} />
        {errorInputs}
        {button('Prévisualiser caméra autotune', 'autotune_camera', () => ({ channel: integer(channel), final_error: errorScenario() }))}
      </div>
      <small>8 frames ; Wait 500/500/3000 ms. Erreur caméra : pas de reset Wait ni saut des étapes moteur démontré.</small>
    </>}
    {section === 'Erreurs' && <div className="elyse-motion-grid">
      <Choice label="Événement journal moteur" value={errorEvent} change={setErrorEvent} options={meta?.error_event_indices || []} disabled={disabled} />
      {errorInputs}
      {button('Prévisualiser journal erreur moteur', 'motor_error', () => ({ event_index: integer(errorEvent), final_error: errorScenario() }))}
      <small>Aucun fichier Erreurs.xls créé ou écrit.</small>
    </div>}
  </div>;
}
