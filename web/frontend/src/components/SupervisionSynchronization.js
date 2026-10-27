import React, { useEffect, useState } from 'react';
import { supervisionCounterClient } from '../api/supervisionCounterClient';
import { COUNTER_STALE_SECONDS, decodeSupervisionCounter } from './supervisionCounterView';
import './SupervisionSynchronization.css';

const initial = () => ({ state: 'WAITING', values: null, age: null, at: null, payload: null, error: '' });
const LABELS = { WAITING: 'En attente de synchronisation', CURRENT: 'Mémoire récente',
  STALE: 'Mémoire périmée', UNAVAILABLE: 'Synchronisation indisponible' };
const COUNTER_NAMES = ['LASER-HF', 'IMAC', 'LASER', 'Osc1', 'Osc2', 'Detect1', 'Detect2', 'Machine'];

export default function SupervisionSynchronization({ client = supervisionCounterClient, enabled = true }) {
  const [view, setView] = useState(initial);
  const [now, setNow] = useState(() => performance.now());
  useEffect(() => {
    setView(initial());
    if (!enabled) return undefined;
    const abort = new AbortController();
    let timer;
    let previous = null;
    const poll = async () => {
      const started = performance.now();
      try {
        const decoded = decodeSupervisionCounter(await client.synchronization(abort.signal));
        if (abort.signal.aborted) return;
        const at = performance.now();
        let age = decoded.age === null ? null : decoded.age + Math.max(0, at - started) / 1000;
        if (decoded.values) {
          const session = decoded.payload.session_id;
          const sequence = decoded.payload.sequence;
          if (previous?.session === session && sequence < previous.sequence) throw new Error('Séquence SuperVision antérieure.');
          if (previous?.session === session && sequence === previous.sequence) {
            age = Math.max(age, previous.age + Math.max(0, at - previous.at) / 1000);
          }
          previous = { session, sequence, age, at };
        }
        setNow(at);
        setView({ ...decoded, age, at, error: '' });
      } catch (error) {
        if (!abort.signal.aborted) setView({ ...initial(), state: 'UNAVAILABLE', error: error.message });
      } finally {
        if (!abort.signal.aborted) timer = setTimeout(poll, 1000);
      }
    };
    poll();
    const clock = setInterval(() => setNow(performance.now()), 250);
    return () => { abort.abort(); clearTimeout(timer); clearInterval(clock); };
  }, [client, enabled]);
  const age = view.age === null ? null : view.age + Math.max(0, now - view.at) / 1000;
  const state = !enabled ? 'UNAVAILABLE' : view.state === 'CURRENT' && age >= COUNTER_STALE_SECONDS ? 'STALE' : view.state;
  const current = state === 'CURRENT' && view.values !== null;
  return <section className="supervision-sync" aria-label="Synchronisation SuperVision en lecture seule">
    <header><h2>Synchronisation SuperVision · NI6602</h2><span>10.20.30.2 · lecture seule</span></header>
    <p role="status" aria-label="État synchronisation SuperVision">{LABELS[state]}</p>
    {view.error && <p role="alert">{view.error}</p>}
    <p>Paramètres lus sur SuperVision. Les impulsions physiques ne sont pas mesurées ici.</p>
    {current && <p>{view.payload.source_mode === 'LABVIEW_BRIDGE' ? 'Contrôles LabVIEW observés' : 'Dernières écritures logicielles réussies'}
      {' · '}âge {age.toFixed(2)} s · observation {view.payload.sequence}
      {' · '}sélecteur {view.payload.selector} · {view.payload.pending_selector ? 'modification en attente' : 'aucune modification en attente'}</p>}
    <table><caption>8 compteurs locaux · paires délai / largeur</caption><thead><tr>
      <th scope="col">Compteur SuperVision</th><th scope="col">Délai (µs)</th><th scope="col">Largeur (µs)</th>
    </tr></thead><tbody>{Array.from({ length: 8 }, (_, index) => <tr key={index}>
      <th scope="row">ctr{index} · {COUNTER_NAMES[index]}</th>
      <td><output aria-label={`SuperVision ctr${index} délai`}>{current ? String(view.values[index * 2]) : '—'}</output></td>
      <td><output aria-label={`SuperVision ctr${index} largeur`}>{current ? String(view.values[index * 2 + 1]) : '—'}</output></td>
    </tr>)}</tbody></table>
  </section>;
}
