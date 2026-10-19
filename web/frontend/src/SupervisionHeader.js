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

export function AcquisitionWatchdog({ telemetry }) {
  const state = acquisitionLinkState(telemetry);
  const connected = state === 'CONNECTED';
  const label = connected ? 'connecté' : state === 'WAITING' ? 'en attente' : 'déconnecté';
  return <div className={`elyse-watchdog elyse-watchdog--${state.toLowerCase()}`}
    role="status" aria-label="Watchdog Acquisition"
    title="Fraîcheur des paquets Acquisition, pas autorisation ni état des équipements.">
    <span className={`elyse-lamp elyse-lamp--${connected ? 'green' : state === 'WAITING' ? 'unknown' : 'red'}`} aria-hidden="true" />
    <span>Watchdog Acquisition : {label}</span>
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
