import React from 'react';
import { useLatestRead } from './useAcquisitionTelemetry';
import './CoolingAlarm.css';

const clock = (value) => {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleTimeString('fr-FR', {
    timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit', second: '2-digit',
  }) : 'heure inconnue';
};

// Display only SERVER incidents/deadlines and confirmations. The shared
// Acquisition command flow owns the explicit operator confirmation action.
export function CoolingAlarmDisplay({ telemetry, safety: suppliedSafety, sourceFailure = '', archiveError = '' }) {
  const safety = suppliedSafety ?? telemetry?.payload?.cooling_safety
    ?? telemetry?.payload?.snapshot?.cooling_safety;
  if (!safety || safety.schema_version !== 1) return null;
  const incidents = Array.isArray(safety.circuits) ? safety.circuits : [];
  const failed = !!(sourceFailure || telemetry?.failure) || (telemetry?.elapsed || 0) >= 2
    || safety.quality !== 'FRESH';
  const active = safety.active === true && incidents.length > 0;
  const unknownWhileActive = safety.machine_active === true && failed;
  if (!active && !unknownWhileActive && !safety.journal_error && !archiveError) return null;
  const remaining = Number.isFinite(safety.remaining_seconds)
    ? Math.max(0, Math.ceil(safety.remaining_seconds - Math.max(0, telemetry?.elapsed || 0))) : null;
  const canStop = safety.automatic_stop_available === true;
  const episodePolicy = typeof safety.countdown_required === 'boolean'
    || typeof safety.confirmation_required === 'boolean';
  const countdown = episodePolicy ? safety.countdown_required === true
    || (safety.countdown_required === undefined && safety.confirmation_required === true) : active;
  const candidates = new Set((Array.isArray(safety.confirmation_candidates) ? safety.confirmation_candidates : [])
    .map((item) => item.incident_id));
  const confirmed = (item) => typeof item.confirmed === 'boolean' ? item.confirmed
    : item.water_confirmation_received === true || (typeof item.confirmed_utc === 'string' && item.confirmed_utc.length > 0);
  return <section className="cooling-alarm" role={active || unknownWhileActive || safety.journal_error ? 'alert' : 'region'} aria-label="Alarme circulation refroidissement">
    {!active && unknownWhileActive && <p>Surveillance refroidissement indisponible : circulation non confirmée.
      Données manquantes ou périmées, pas preuve de circulation normale. Intervention locale nécessaire.</p>}
    {active && <><h2>{episodePolicy ? 'SIGNAL REFROIDISSEMENT ROUGE' : 'PERTE DE CIRCULATION'} — {incidents.map((item) => item.circuit).join(' + ')}</h2>
      {incidents.map((item) => <div key={item.circuit}><strong>{item.circuit}</strong>
        {item.started_utc && <>{' · détectée à '}{clock(item.started_utc)}</>}
        {(!episodePolicy || (!confirmed(item) && candidates.has(item.incident_id))) && <>{' · échéance '}{clock(item.deadline_utc)}</>}
        {episodePolicy && confirmed(item) && <small> · Circulation physique confirmée par {item.confirmed_by || 'l’opérateur'}
          {item.confirmed_utc && <> à {clock(item.confirmed_utc)}</>}. Arrêt supplémentaire de 120 s annulé pour cet incident uniquement.
          Le signal rouge reste affiché. Les règles de la garde VI restent inchangées.</small>}
        {item.causes?.length > 0 && <small>{' · '}{item.causes.map((cause) =>
          ({ '220V': 'alimentation 220 V', controller_fault: 'défaut régulateur', pressure: 'pressostat', flow: 'débitmètre' })[cause.signal]
          || cause.signal).join(', ')}</small>}</div>)}
      {safety.stop_state === 'NONE' && countdown ? <p>COUNTDOWN — {remaining === null ? 'inconnu' : `${remaining} s`}.
        {' '}Rétablissez la circulation d’eau.{canStop
          ? ' Sinon le serveur demandera l’arrêt forcé de l’accélérateur à l’échéance.'
          : ' Arrêt automatique NON DISPONIBLE sur cette source. Intervention locale nécessaire.'}</p>
        : safety.stop_state !== 'NONE' ? <p>Procédure d’arrêt : {safety.stop_state}{safety.stop_error && ` — ${safety.stop_error}`}</p>
          : <p>Aucun arrêt supplémentaire de 120 s en attente pour les incidents confirmés ou les signaux rouges initiaux.
            Les règles de la garde VI restent inchangées.</p>}
      {failed && <p>Retour de circulation non confirmé par les entrées : télémétrie périmée ou indisponible.
        {countdown && ' Le délai serveur n’est pas annulé.'}</p>}
      {!canStop && <p>Récepteur en lecture seule ou chaîne d’arrêt non qualifiée : aucune promesse d’arrêt matériel.</p>}</>}
    {safety.journal_error && <p>ERREUR JOURNAL : {safety.journal_error}</p>}
    {archiveError && <p role="alert">ERREUR ARCHIVAGE WEB : {archiveError}</p>}
  </section>;
}

export function CoolingAlarmView({ remote, telemetry, enabled = true }) {
  const safety = remote.payload?.cooling_safety;
  if (!enabled) return <CoolingAlarmDisplay telemetry={telemetry} />;
  const unavailable = remote.failure || (remote.elapsed >= 2 ? 'retour serveur périmé' : '');
  return <><CoolingAlarmDisplay safety={safety} telemetry={{ elapsed: remote.elapsed }} sourceFailure={remote.failure}
    archiveError={remote.payload?.archive_error} />
    {unavailable && safety?.active !== true && <div className="cooling-alarm" role="alert">Alarme refroidissement indisponible — {unavailable}.
      Aucun état normal ni arrêt automatique ne peut être confirmé.</div>}</>;
}

export default function CoolingAlarm({ client, telemetry }) {
  const enabled = typeof client?.coolingSafety === 'function';
  const remote = useLatestRead(client, 'coolingSafety', enabled);
  return <CoolingAlarmView remote={remote} telemetry={telemetry} enabled={enabled} />;
}
