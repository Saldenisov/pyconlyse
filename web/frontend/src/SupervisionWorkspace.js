import React, { useState } from 'react';
import { readBankField } from './elyseLiveProjection';
import workspace from './elyseSupervisionWorkspace.json';
import synoptic from './assets/elyse-synoptique-original.png';
import './SupervisionWorkspace.css';

const EMPTY = { payload: null, failure: '', elapsed: 0 };

export function lineValue(binding, telemetry = EMPTY) {
  return readBankField(telemetry.payload, binding.bank, binding.index, 'number', telemetry.elapsed, telemetry.failure);
}

export function lineNumber(value, format) {
  const fixed = /^%\.(\d)f$/.exec(format);
  if (fixed) return value.toFixed(Number(fixed[1])).replace('.', ',');
  if (format === '%.2g') return value.toLocaleString('fr-FR', { maximumSignificantDigits: 2, useGrouping: false });
  // LabVIEW-specific %#_g stays recorded as provenance; no invented decimal scale.
  return value.toLocaleString('fr-FR', { maximumSignificantDigits: 6, useGrouping: false });
}

function Command({ children, label, purpose, nativeUid, actionCode }) {
  return <button type="button" disabled aria-label={label}
    data-native-uid={nativeUid} data-action-code={actionCode}
    title={purpose ? `${purpose} Commande non connectée.` : 'Commande non connectée'}>{children}</button>;
}

export function lineButtonPurpose(control) {
  if (control.role === 'power') {
    return 'Commande Marche / Arrêt du bloc. État de commande non transmis ; retour « en marche » distinct.';
  }
  if (control.role === 'step_mode') {
    return 'Sélection du pas de réglage x1 / x10. Position actuelle non transmise.';
  }
  const direction = control.role.endsWith('decrease') ? 'Diminuer' : 'Augmenter';
  const scale = control.role.startsWith('coarse') ? 'grand pas' : 'petit pas';
  const choices = control.step_choices?.map((step) => step.toLocaleString('fr-FR')).join(' ou ');
  return `${direction} la consigne — ${scale}${choices ? ` : ${choices} ${control.unit}` : ''}. Le pas dépend de X1/X10 ; position non transmise.`;
}

function LineCommand({ row, control }) {
  const name = control.role === 'power' ? 'Marche / Arrêt'
    : control.role === 'step_mode' ? 'X1 / X10' : control.label;
  return <Command label={`${row.label} · ${name}`} purpose={lineButtonPurpose(control)}
    nativeUid={control.native_uid} actionCode={control.action_code}>{control.label}</Command>;
}

function LineReading({ row, field, telemetry }) {
  const binding = row[field];
  const result = lineValue(binding, telemetry);
  const label = field === 'consigne' ? 'Consigne ACQ' : 'Lecture';
  return <div className={`sup-line__value sup-line__value--${field}`}
    title={`${binding.bank}[${binding.index}] · ${result.quality} · format VI ${row.native_formats[field]}`}>
    <small>{label}</small><output aria-label={`${row.label} · ${label}`}>
      {result.quality === 'FRESH' ? lineNumber(result.value, row.native_formats[field]) : '—'}
    </output><span>{row.unit}</span>
  </div>;
}

export function BeamLinePanel({ line, telemetry = EMPTY }) {
  const definition = workspace.lines[line];
  const title = line === 'direct' ? 'Voie directe' : 'Voie déviée';
  return <section className="sup-line" aria-label={title}>
    <h2>{title}</h2>
    <div className="sup-line__viewport"><div className="sup-line__grid">
      {[...definition.rows].sort((a, b) => a.row - b.row || a.column - b.column).map((row) => <section
        className={`sup-line__card${row.label.startsWith('Dipôle') ? ' sup-line__card--dipole' : row.unit === '°' ? ' sup-line__card--phase' : ''}`}
        key={row.uid} aria-label={row.label}
        style={{ gridColumn: row.column, gridRow: row.row }}>
        <div className="sup-line__toolbar">
          <LineCommand row={row} control={row.native_buttons[0]} />
          <div className="sup-line__states" aria-label={`${row.label} · états non qualifiés`}>
            {['en marche', 'écart consigne / lecture', 'en défaut'].map((state) =>
              <span key={state} role="img" aria-label={`${row.label} · ${state} inconnu`} />)}
          </div>
          <LineCommand row={row} control={row.native_buttons[1]} />
        </div>
        <div className="sup-line__range" title="Libellé du VI, pas une limite matérielle vérifiée">{row.native_range_label}</div>
        <h3>{row.label}</h3>
        <div className="sup-line__readings">
          <LineReading row={row} field="consigne" telemetry={telemetry} />
          <LineReading row={row} field="lecture" telemetry={telemetry} />
        </div>
        <div className="sup-line__arrows">{row.native_buttons.slice(2).map((control) =>
          <LineCommand key={control.native_uid} row={row} control={control} />)}</div>
      </section>)}
    </div></div>
  </section>;
}

export function SynopticPanel() {
  return <section className="sup-synoptic" aria-label="Synoptique ELYSE">
    <h2>Synoptique ELYSE</h2>
    <figure><img src={synoptic} width="866" height="596" alt="Synoptique ELYSE original : canon, section accélératrice, dipôles et lignes de transport" />
      <figcaption>Plan d’origine · statique</figcaption></figure>
  </section>;
}

export function NewFocusPanel() {
  const [host, setHost] = useState('');
  const [device, setDevice] = useState('');
  const [pair, setPair] = useState('');
  const [steps, setSteps] = useState('');
  return <section className="sup-integration" aria-label="NewFocus Picomotor">
    <h2>NewFocus · Picomotor</h2><p className="sup-integration__state">Non connecté</p>
    <div className="sup-integration__columns">
      <fieldset><legend>Connexion · préparation locale</legend>
        <label>IP du contrôleur<input aria-label="IP NewFocus" value={host} placeholder="Adresse à confirmer"
          onChange={(event) => setHost(event.target.value)} /></label>
        <label>Device Tango<input aria-label="Device Tango NewFocus" value={device} placeholder="Device à enregistrer"
          onChange={(event) => setDevice(event.target.value)} /></label>
        <Command label="Connecter NewFocus">Connecter</Command>
      </fieldset>
      <fieldset><legend>Axes X / Y</legend>
        <label>Paire native<select aria-label="Paire de moteurs NewFocus" value={pair} onChange={(event) => setPair(event.target.value)}>
          <option value="">À confirmer</option><option value="3,4">Laser 1 · moteurs 3 / 4</option>
          <option value="1,2">Laser 2 · moteurs 1 / 2</option></select></label>
        <label>Pas relatifs<input aria-label="Pas relatifs NewFocus" type="number" step="1" value={steps}
          onChange={(event) => setSteps(event.target.value)} /></label>
        <div className="sup-integration__jog">{['X−', 'X+', 'Y−', 'Y+'].map((axis) =>
          <Command key={axis} label={`NewFocus · ${axis}`}>{axis}</Command>)}</div>
        <div className="sup-integration__actions"><Command label="Arrêter NewFocus">Arrêter</Command>
          <Command label="Autotune NewFocus">Autotune</Command></div>
      </fieldset>
    </div>
    <div className="sup-integration__counters">{[1, 2, 3, 4].map((axis) =>
      <div key={axis}><span>Moteur {axis}</span><output aria-label={`Compteur moteur ${axis}`}>—</output><small>pas</small></div>)}</div>
  </section>;
}

export function EthernetCameraPanel() {
  const [model, setModel] = useState('');
  const [endpoint, setEndpoint] = useState('');
  return <section className="sup-integration" aria-label="Caméra Ethernet">
    <h2>Caméra Ethernet</h2><p className="sup-integration__state">Non connectée</p>
    <div className="sup-camera__layout"><div className="sup-camera__image" role="img" aria-label="Aucune image caméra reçue">
      Aucune image reçue</div><fieldset><legend>Connexion · préparation locale</legend>
      <label>Modèle<input aria-label="Modèle caméra Ethernet" value={model} placeholder="Modèle à préciser"
        onChange={(event) => setModel(event.target.value)} /></label>
      <label>IP / Device Tango<input aria-label="Adresse caméra Ethernet" value={endpoint} placeholder="Adresse à préciser"
        onChange={(event) => setEndpoint(event.target.value)} /></label>
      <Command label="Connecter caméra Ethernet">Connecter</Command>
      <div className="sup-integration__actions"><Command label="Acquérir image Ethernet">Acquérir</Command>
        <Command label="Arrêter caméra Ethernet">Arrêter</Command></div>
</fieldset></div>
  </section>;
}
