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
    // Saved action-mask 1 handlers pass seven values unchanged. The M/A label
    // is not a proved power-switch path (beam_switch_trace_20261016/RESULT.json).
    return 'Libellé M/A du VI. Valeurs conservées dans les branches auditées ; aucune commande matérielle Marche / Arrêt démontrée. Les banques analogiques peuvent être republiées.';
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
  const name = control.role === 'power' ? 'M/A'
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
    <details className="sup-workspace__details"><summary>Sources et commandes</summary>
      <p>Consignes ACQ et lectures C1 séparées. Aucun état M/A ou X1/X10 supposé depuis une valeur enregistrée.</p>
      <p>M/A : sept valeurs conservées dans les branches auditées ; aucune commande matérielle Marche / Arrêt démontrée.
        X1/X10 : sélection du pas,
        pas multiplication du courant mesuré. Les positions actuelles de ces deux commandes ne sont pas transmises.</p>
      <p>Correcteurs : &lt;&lt; / &gt;&gt; diminuent / augmentent la consigne par grand pas (0,1 ou 1 A) ;
        &lt; / &gt; par petit pas (0,01 ou 0,1 A), selon X1/X10.</p>
      <p>Les plages affichées viennent des libellés du VI ;
        ce ne sont pas des limites matérielles validées. Les quatre colonnes natives restent fixes, même en fenêtre étroite.</p>
      <p>Les flèches natives ajustent les consignes. Seuls les changements des bits 7–10 passent la garde de transfert ;
        les quatre banques C6–C9 peuvent ensuite être republiées même sans nouveau transfert. Aucune publication depuis cette page.</p>
      {workspace.limits.map((limit) => <p key={limit}>{limit}</p>)}
      <table><thead><tr><th>Élément</th><th>Consigne ACQ</th><th>Lecture</th></tr></thead>
        <tbody>{definition.rows.map((row) => <tr key={row.uid}><th>{row.label}</th>
          <td>{row.consigne.bank}[{row.consigne.index}]</td><td>{row.lecture.bank}[{row.lecture.index}]</td></tr>)}</tbody></table>
    </details>
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
        <p>Adaptateur disponible : DS_Picomotor8742 · Ethernet</p>
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
    <details className="sup-workspace__details"><summary>Connexion et logique du VI</summary>
      <p>Variables locales : référence CmdLib .NET, DeviceKey, Device Address, numéros de moteurs et pas relatifs.
        Ce ne sont pas des adresses de cartes Acquisition.</p>
      <p>Initialisation native : InitSingleDevice (5000 ms) → GetIdentification → SetZeroPosition (1…4).
        Le nouveau DS n’applique pas cette remise à zéro automatiquement.</p>
      <p>Déplacement natif : RelativeMove, puis GetMotionDone / GetPosition / erreur / arrêt.
        La correspondance physique des axes et les limites restent à confirmer.</p>
      <p>DS existant : TCP 23 ; host et identité à confirmer, motion_enabled=False par défaut.
        TP? est un compteur de pas, pas une position mécanique mesurée. Aucun scan ni connexion lancé ici.</p>
    </details>
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
      <p>Modèle et source du flux à confirmer.</p></fieldset></div>
  </section>;
}
