import React, { useState } from 'react';
import { readBankField } from './elyseLiveProjection';
import header from './elyseSupervisionHeader.json';

export function acquisitionLinkState({ payload, failure, elapsed = 0 }) {
  if (failure) return 'UNAVAILABLE';
  if (!payload?.snapshot) return 'WAITING';
  if (payload.server_state !== 'ON') return 'UNAVAILABLE';
  const snapshot = payload.snapshot;
  if (typeof snapshot.receiver_session !== 'string' || !snapshot.receiver_session
      || !Number.isSafeInteger(snapshot.received_this_process) || snapshot.received_this_process <= 0) return 'WAITING';
  const records = Object.values(snapshot.publications || {});
  const fresh = records.some((record) => record.stale === false
    && Number.isFinite(record.age_seconds) && record.age_seconds >= 0
    && Number.isFinite(elapsed) && elapsed >= 0
    && record.age_seconds + elapsed < Math.min(2, payload.stale_after_seconds || 2));
  return fresh ? 'CONNECTED' : records.length ? 'STALE' : 'WAITING';
}

export function frequencyReadback(telemetry) {
  const row = readBankField(telemetry.payload, header.telemetry_bank, header.telemetry_index,
    'number', telemetry.elapsed, telemetry.failure);
  return row.quality === 'FRESH' && header.choices.some((choice) => choice.value === row.value)
    ? String(row.value) : '';
}

export function acquisitionProblems(telemetry, cooling) {
  const issues = [];
  const add = (level, text) => issues.push({ level, text });
  const state = acquisitionLinkState(telemetry);
  if (state === 'UNAVAILABLE') add(2, telemetry.failure || telemetry.payload?.error
    || `Récepteur Acquisition : ${telemetry.payload?.server_state || 'indisponible'}`);
  if (state === 'WAITING') add(1, 'En attente de paquets Acquisition');
  if (state === 'STALE') add(1, 'Flux Acquisition périmé');
  const payload = telemetry.payload;
  const records = payload?.snapshot?.publications || {};
  Object.entries(records).forEach(([name, bank]) => {
    const error = bank.error || {};
    if (error.status === true || (typeof error.code === 'number' && error.code !== 0)) {
      const unread = error.code === -80001 && bank.data === null;
      add(unread ? 1 : 2, `${name} : ${unread ? 'entrées non lues' : 'erreur de lecture'} (${error.code})${error.source ? ` · ${error.source}` : ''}`);
    } else if (bank.stale !== false || !Number.isFinite(bank.age_seconds)
        || bank.age_seconds < 0 || !Number.isFinite(telemetry.elapsed ?? 0)
        || bank.age_seconds + (telemetry.elapsed || 0) >= Math.min(2, payload.stale_after_seconds || 2)) {
      add(1, `${name} : données périmées ou indisponibles`);
    }
  });
  const missing = (payload?.expected_banks || []).filter((name) => !records[name]);
  if (missing.length) add(1, `Banques manquantes : ${missing.join(', ')}`);
  if (state === 'CONNECTED' && payload?.quality && payload.quality !== 'FRESH' && !issues.length) {
    add(payload.quality === 'READ_ERROR' ? 2 : 1, `Télémétrie : ${payload.quality}`);
  }

  // An explicitly selected cooling response never falls back to another source.
  const safety = cooling !== undefined ? cooling.payload?.cooling_safety
    : payload?.cooling_safety ?? payload?.snapshot?.cooling_safety;
  if (cooling?.failure) add(2, `Alarme refroidissement indisponible : ${cooling.failure}`);
  else if (cooling && !safety) add(1, 'Alarme refroidissement : en attente de réponse');
  if (cooling?.elapsed >= 2) add(1, 'Retour refroidissement périmé');
  if (safety && safety.schema_version !== 1) add(2, 'Contrat alarme refroidissement incompatible');
  if (safety?.schema_version === 1) {
    if (safety.quality !== 'FRESH') add(1, `Refroidissement : données ${safety.quality || 'UNKNOWN'}`);
    if (safety.active === true) {
      (safety.circuits || []).forEach((item) => {
        const causes = (item.causes || []).map((cause) => cause.signal).filter(Boolean);
        add(2, `${item.circuit} : signal refroidissement rouge${causes.length ? ` (${causes.join(', ')})` : ''}`);
      });
      if (safety.automatic_stop_available !== true) add(2, 'Arrêt automatique indisponible');
    }
    if (safety.countdown_required === true || safety.confirmation_required === true
        || (safety.countdown_required === undefined && safety.confirmation_required === undefined
            && safety.active === true && safety.stop_state === 'NONE')) {
      const seconds = Number.isFinite(safety.remaining_seconds)
        ? Math.max(0, Math.ceil(safety.remaining_seconds - Math.max(0, cooling?.elapsed ?? telemetry.elapsed ?? 0))) : null;
      add(2, `COUNTDOWN : ${seconds === null ? 'délai inconnu' : `${seconds} s`}`);
    }
    if (['FAILED', 'INTERRUPTED', 'REQUESTED', 'UNAVAILABLE'].includes(safety.stop_state)) {
      add(['FAILED', 'INTERRUPTED'].includes(safety.stop_state) ? 2 : 1,
        `Arrêt : ${safety.stop_state}${safety.stop_error ? ` · ${safety.stop_error}` : ''}`);
    }
    if (safety.journal_error) add(2, `Journal source : ${safety.journal_error}`);
  }
  if (cooling?.payload?.archive_error) add(2, `Archivage Web : ${cooling.payload.archive_error}`);
  return issues.sort((a, b) => b.level - a.level);
}

export function AcquisitionWatchdogDetails({ telemetry, cooling }) {
  const problems = acquisitionProblems(telemetry, cooling);
  return problems.length ? <section aria-label="Problèmes observés actuellement"><h3>Problèmes observés actuellement</h3>
    <ul>{problems.map((item, index) => <li key={index}>{item.text}</li>)}</ul></section> : null;
}

export function AcquisitionWatchdog({ telemetry, cooling, onOpenJournal }) {
  const state = acquisitionLinkState(telemetry);
  const connected = state === 'CONNECTED';
  const problems = acquisitionProblems(telemetry, cooling);
  const severity = problems[0]?.level || 0;
  const label = connected ? 'connecté' : state === 'WAITING' ? 'en attente'
    : state === 'STALE' ? 'données périmées' : 'déconnecté';
  const text = `Watchdog Acquisition : ${label}${problems.length ? ` · ${problems.slice(0, 2).map((item) => item.text).join(' · ')}` : ''}`
    + (problems.length > 2 ? ` · +${problems.length - 2} autres problèmes` : '');
  return <div className={`elyse-watchdog elyse-watchdog--${state.toLowerCase()}${severity === 2 ? ' elyse-watchdog--fault' : severity === 1 ? ' elyse-watchdog--warning' : ''}`}
    role="status" aria-label="Watchdog Acquisition"
    title={['Fraîcheur des paquets et problèmes observés ; état physique non établi.', ...problems.map((item) => item.text)].join('\n')}>
    <span className={`elyse-lamp elyse-lamp--${severity === 2 ? 'red' : severity === 1 ? 'amber' : 'green'}`} aria-hidden="true" />
    {onOpenJournal ? <button type="button" className="elyse-watchdog__message" onClick={onOpenJournal}
      aria-label="Ouvrir le journal des alarmes">{text}</button> : <span className="elyse-watchdog__message">{text}</span>}
  </div>;
}

export function MachineFrequency({ telemetry }) {
  const [draft, setDraft] = useState(null);
  const readback = frequencyReadback(telemetry);
  return <div className="elyse-frequency">
    <label htmlFor="elyse-machine-frequency">Fréquence machine{draft !== null && ' · brouillon'}</label>
    <select id="elyse-machine-frequency" aria-label="Fréquence machine" value={draft ?? readback}
      title="Choix local non transmis. Aucune commande PSP, Tango ou NI."
      onChange={(event) => setDraft(event.target.value === readback ? null : event.target.value)}>
      <option value="" disabled>—</option>
      {header.choices.map((choice) => <option key={choice.value} value={String(choice.value)}>{choice.label}</option>)}
    </select>
  </div>;
}
