import React, { useEffect, useRef, useState } from 'react';
import { readBankField } from './elyseLiveProjection';
import './CoolingOperationalAlert.css';

// Operator annunciation, independent of countdown/shutdown/acknowledgment policy.
// Same input polarity as Fluides and tools/elyse_cooling_alert.py on Everest.
export const COOLING_220V = { CANON: 0, SECTION: 6 };
export function newCoolingWatch() {
  return { general: false, armed: new Set(), faults: new Set(), recovering: {}, progress: {} };
}
export function observeCooling(watch, telemetry, now) {
  const { payload, elapsed = 0, failure = '' } = telemetry || {};
  const read = (bank, index) => {
    const item = readBankField(payload, bank, index, 'boolean', elapsed, failure);
    if (item.quality !== 'FRESH') return null;
    const record = payload.snapshot.publications[bank];
    if (typeof record.session_id !== 'string' || !record.session_id
      || !Number.isInteger(record.sequence) || record.sequence < 0) return null;
    const identity = `${record.session_id}:${record.sequence}`;
    const previous = watch.progress[bank];
    if (previous?.identity !== identity) watch.progress[bank] = { identity, changed: now };
    return now - watch.progress[bank].changed >= 2 ? null : item.value;
  };
  const general = read('EPS', 8);
  const circuits = Object.fromEntries(Object.entries(COOLING_220V).map(([name, index]) => [name, read('C3_IN_DIO96', index)]));
  const banks = payload?.snapshot?.publications;
  if (banks?.EPS?.session_id !== banks?.C3_IN_DIO96?.session_id) {
    Object.keys(circuits).forEach((name) => { circuits[name] = null; });
  }
  if (general !== null) watch.general = general;
  const unknown = general === null || (watch.general && Object.values(circuits).some((value) => value === null));
  if (general === false) {
    watch.armed.clear(); watch.faults.clear(); watch.recovering = {};
  } else if (general === true) {
    Object.entries(circuits).forEach(([name, value]) => {
      if (value === false) {
        watch.armed.add(name);
        if (watch.faults.has(name)) {
          if (watch.recovering[name] === undefined) watch.recovering[name] = now;
          if (now - watch.recovering[name] >= 2) {
            watch.faults.delete(name); delete watch.recovering[name];
          }
        }
      } else {
        delete watch.recovering[name];
        if (value === true && watch.armed.has(name)) watch.faults.add(name);
      }
    });
  }
  if (unknown) watch.recovering = {};
  return { faults: [...watch.faults].sort(), monitoringLost: unknown && watch.general };
}

export default function CoolingOperationalAlert({ telemetry, onOpenJournal }) {
  const watch = useRef(newCoolingWatch());
  const [alarm, setAlarm] = useState({ faults: [], monitoringLost: false });
  useEffect(() => {
    setAlarm(observeCooling(watch.current, telemetry, performance.now() / 1000));
  }, [telemetry]);
  if (!alarm.faults.length && !alarm.monitoringLost) return null;
  return <section className="cooling-operational-alert" role="alert" aria-label="Alerte immédiate refroidissement">
    <strong>ALARME REFROIDISSEMENT{alarm.faults.length ? ` — ${alarm.faults.join(' + ')}` : ' — SURVEILLANCE PERDUE'}</strong>
    {alarm.faults.length > 0 && <p>Retour Secteur 220 V devenu rouge pendant le fonctionnement.</p>}
    {alarm.monitoringLost && <p>Télémétrie indisponible : circulation non confirmée. L’alarme reste active.</p>}
    <p>Vérifier immédiatement le moteur et la circulation d’eau ; rétablir le refroidissement ou arrêter la machine selon la procédure locale.</p>
    <small>Aucune commande automatique envoyée par cette alerte.</small>
    {onOpenJournal && <button type="button" onClick={onOpenJournal}>Voir les détails</button>}
  </section>;
}
