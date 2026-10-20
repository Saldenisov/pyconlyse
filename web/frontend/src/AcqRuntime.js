import React, { useState } from 'react';
import useAcqRuntime from './useAcqRuntime';
import { ACQ_RUNTIME_BANKS } from './api/acqRuntimeClient';
import './AcqRuntime.css';

export const RUNTIME_BANKS = ACQ_RUNTIME_BANKS;
const QUALITY = { FRESH: 'Lecture NI récente', STALE: 'Mesures périmées · masquées', UNAVAILABLE: 'Serveur indisponible',
  INCOMPATIBLE: 'Version incompatible', RECOVERY_REQUIRED: 'Récupération requise', IDLE: 'Serveur en attente',
  EXECUTING: 'Procédure en cours', FAULT: 'Défaut serveur' };

function ageText(value, elapsed) {
  return Number.isFinite(value) ? `${(value + elapsed).toFixed(1)} s` : '—';
}
function valueText(value) {
  if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE';
  return Number.isFinite(value) ? String(value) : '—';
}
export function runtimeBank(payload, name) {
  if (payload?.quality !== 'FRESH') return null;
  const definition = RUNTIME_BANKS.find(([bank]) => bank === name);
  if (!definition) return null;
  const bank = payload.snapshot?.runtime?.latest?.banks?.[name];
  if (!bank || bank.kind !== definition[2] || !Array.isArray(bank.values) || bank.values.length !== definition[1]
      || !bank.values.every((value) => definition[2] === 'digital_input' ? typeof value === 'boolean'
        : typeof value === 'number' && Number.isFinite(value))) return null;
  return bank;
}

export default function AcqRuntime({ client }) {
  const { payload, failure, elapsed, sessionChanged, retrySeconds } = useAcqRuntime(client);
  const [selected, setSelected] = useState(RUNTIME_BANKS[0][0]);
  const raw = payload?.snapshot?.runtime;
  const bank = runtimeBank(payload, selected);
  const definition = RUNTIME_BANKS.find(([name]) => name === selected);
  const quality = failure ? 'UNAVAILABLE' : payload?.quality || 'UNAVAILABLE';
  const scaled = bank?.legacy_scaled_values;
  const scaledValid = definition[2] === 'analog_input' && Array.isArray(scaled) && scaled.length === definition[1]
    && scaled.every((value) => typeof value === 'number' && Number.isFinite(value));
  return <div className="acq-runtime">
    <div className={`acq-runtime__status acq-runtime__status--${quality.toLowerCase()}`} role="status" aria-label="État Python Acquisition">
      <strong>{QUALITY[quality]}</strong><span>Python Acquisition · lecture seule</span>
    </div>
    <p className="acq-runtime__boundary">Connexion perdue ou récupération requise ≠ équipement arrêté. Aucune commande matérielle depuis cette page.</p>
    {failure && <p role="alert" className="acq-runtime__error">{failure} Nouvelle tentative dans {retrySeconds} s.</p>}
    {sessionChanged && <p className="acq-runtime__notice">Nouvelle session du serveur : anciennes mesures supprimées.</p>}
    <dl className="acq-runtime__metrics">
      <div><dt>État du serveur</dt><dd>{raw?.state || payload?.runtime_state || '—'}</dd></div>
      <div><dt>Transport Everest</dt><dd>{ageText(payload?.bridge_age_seconds, elapsed)}</dd></div>
      <div><dt>Lecture NI</dt><dd>{ageText(payload?.source_age_seconds, elapsed)}</dd></div>
      <div><dt>Opération</dt><dd>{raw?.current_operation || '—'}</dd></div>
      <div><dt>Récupération</dt><dd>{raw?.recovery?.required === true ? 'REQUISE'
        : raw?.recovery?.required === false ? 'Non requise' : '—'}</dd></div>
      <div><dt>Révision d’état</dt><dd>{raw?.state_revision ?? '—'}</dd></div>
    </dl>
    {raw?.recovery?.protection_active === false && <p className="acq-runtime__warning" role="alert">Barrière de propriété persistante inactive : observation uniquement, récupération automatique non qualifiée.</p>}
    {(raw?.error || (raw?.recovery?.required && raw.recovery.reason))
      && <p className="acq-runtime__error" role="alert">{raw.error || raw.recovery.reason}</p>}
    {!raw?.recovery?.required && raw?.recovery?.reason && <p className="acq-runtime__notice">Diagnostic de récupération : {raw.recovery.reason}</p>}
    <div className="acq-runtime__identity"><span>Session <code>{payload?.session_id || '—'}</code></span>
      <span>Version <code>{payload?.build_id || '—'}</code></span></div>
    <div className="acq-runtime__content"><nav className="acq-runtime__banks" aria-label="Banques Python Acquisition">
      {RUNTIME_BANKS.map(([name, count, kind]) => <button type="button" key={name} aria-pressed={selected === name}
        onClick={() => setSelected(name)}><strong>{name}</strong><small>{count} {kind === 'analog_input' ? 'DBL · V' : 'Boolean'} · {runtimeBank(payload, name) ? 'récent' : 'absent / masqué'}</small></button>)}
    </nav><section className="acq-runtime__values" aria-label={`Mesures ${selected}`}><h2>{selected}</h2>
      <p>{bank ? 'Lectures séquentielles, non atomiques entre cartes.' : 'Aucune mesure actuelle validée pour cette banque.'}</p>
      <div className="acq-runtime__table"><table aria-label={`Canaux ${selected}`}><thead><tr><th>Canal</th><th>Type</th>
        <th>{definition[2] === 'analog_input' ? 'Lecture brute · V' : 'Entrée numérique'}</th>{scaledValid && <th>Transformation historique · unité non qualifiée</th>}</tr></thead>
        <tbody>{Array.from({ length: definition[1] }, (_, index) => <tr key={index}><th scope="row">{index}</th>
          <td>{definition[2] === 'analog_input' ? 'DBL' : 'Boolean'}</td><td><output>{bank ? valueText(bank.values[index]) : '—'}</output></td>
          {scaledValid && <td>{valueText(scaled[index])}</td>}</tr>)}</tbody></table></div>
    </section></div>
    <small className="acq-runtime__notice">6 banques d’entrées Python, pas les 27 banques LabVIEW. Dernières valeurs en RAM seulement ; aucun repli PSP/LabVIEW.</small>
  </div>;
}
