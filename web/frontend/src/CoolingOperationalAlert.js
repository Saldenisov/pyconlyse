import React, { useEffect, useRef, useState } from 'react';
import { readBankField } from './elyseLiveProjection';
import './CoolingOperationalAlert.css';
import { newTemperatureWatch, observeTemperature } from './coolingTemperature';

// Operator annunciation, independent of countdown/shutdown/acknowledgment policy.
// Same input polarity as Fluides and tools/elyse_cooling_alert.py on Everest.
export const COOLING_220V = { CANON: 0, SECTION: 6 };
export function newCoolingWatch() {
  return { operating: false, armed: new Set(), faults: new Set(), recovering: {}, progress: {}, temperature: newTemperatureWatch() };
}
export function observeCooling(watch, telemetry, now) {
  const { payload, elapsed = 0, failure = '' } = telemetry || {};
  const read = (bank, index, kind = 'boolean') => {
    const item = readBankField(payload, bank, index, kind, elapsed, failure);
    if (item.quality !== 'FRESH') return null;
    const record = payload.snapshot.publications[bank];
    if (typeof record.session_id !== 'string' || !record.session_id
      || !Number.isInteger(record.sequence) || record.sequence < 0) return null;
    const identity = `${record.session_id}:${record.sequence}`;
    const previous = watch.progress[bank];
    if (previous?.identity !== identity) watch.progress[bank] = { identity, changed: now };
    return now - watch.progress[bank].changed >= 2 ? null : item.value;
  };
  // Fluides Marche régulation -> Marche refroidissement -> EPS[2] OK.
  // General alone must never enable this operational alarm.
  const regulation = read('EPS', 2);
  const chauffage = read('EPS', 14);
  const operating = regulation === null || chauffage === null ? null : regulation && chauffage;
  const circuits = Object.fromEntries(Object.entries(COOLING_220V).map(([name, index]) => [name, read('C3_IN_DIO96', index)]));
  const banks = payload?.snapshot?.publications;
  if (banks?.EPS?.session_id !== banks?.C3_IN_DIO96?.session_id) {
    Object.keys(circuits).forEach((name) => { circuits[name] = null; });
  }
  if (operating !== null) watch.operating = operating;
  const unknown = operating === null || (watch.operating && Object.values(circuits).some((value) => value === null));
  if (operating === false) {
    watch.armed.clear(); watch.faults.clear(); watch.recovering = {};
  } else if (operating === true) {
    Object.entries(circuits).forEach(([name, value]) => {
      if (value !== null) watch.armed.add(name);
      if (value === false) {
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
  const readings = {};
  if (operating === true && banks?.EPS?.session_id === banks?.C1NI6071E?.session_id
    && banks?.EPS?.session_id === banks?.C8NI6703?.session_id) {
    [['CANON', 0, 1], ['SECTION', 8, 2]].forEach(([name, ti, si]) => {
      const temperature = read('C1NI6071E', ti, 'number');
      const setpoint = read('C8NI6703', si, 'number');
      if (temperature !== null && setpoint !== null) readings[name] = { temperature, setpoint,
        session: banks.EPS.session_id, key: `${banks.C1NI6071E.sequence}:${banks.C8NI6703.sequence}` };
    });
  }
  const thermal = observeTemperature(watch.temperature, operating, readings, now);
  return { faults: [...watch.faults].sort(), monitoringLost: unknown && watch.operating,
    temperature: thermal.warnings };
}

export default function CoolingOperationalAlert({ telemetry, onOpenJournal }) {
  const watch = useRef(newCoolingWatch());
  const [alarm, setAlarm] = useState({ faults: [], monitoringLost: false, temperature: [] });
  useEffect(() => {
    setAlarm(observeCooling(watch.current, telemetry, performance.now() / 1000));
  }, [telemetry]);
  if (!alarm.faults.length && !alarm.monitoringLost && !alarm.temperature.length) return null;
  const warningOnly = !alarm.faults.length && !alarm.monitoringLost;
  return <section className={`cooling-operational-alert${warningOnly ? ' cooling-operational-alert--warning' : ''}`} role="alert" aria-label="Alerte immédiate refroidissement">
    <strong>{warningOnly ? 'AVERTISSEMENT TEMPÉRATURE' : 'ALARME REFROIDISSEMENT'}{alarm.faults.length ? ` — ${alarm.faults.join(' + ')}` : alarm.monitoringLost ? ' — SURVEILLANCE PERDUE' : ''}</strong>
    {alarm.faults.length > 0 && <p>Retour Secteur 220 V rouge avec Chauffage et régulation activés.</p>}
    {alarm.monitoringLost && <p>Télémétrie indisponible : circulation non confirmée. L’alarme reste active.</p>}
    {alarm.temperature.map((t) => <p key={t.circuit}>{t.circuit} : {t.temperature_c.toFixed(2)} °C ; consigne {t.setpoint_c.toFixed(2)} °C ; écart +{t.deviation_c.toFixed(2)} °C.
      {' '}Refroidissement dégradé possible : température montée au-dessus de la consigne.
      {t.quality !== 'FRESH' && ' Lecture périmée : retour normal non confirmé.'}</p>)}
    <p>Vérifier immédiatement le moteur et la circulation d’eau ; rétablir le refroidissement ou arrêter la machine selon la procédure locale.</p>
    <small>Aucune commande automatique envoyée par cette alerte.</small>
    {onOpenJournal && <button type="button" onClick={onOpenJournal}>Voir les détails</button>}
  </section>;
}
