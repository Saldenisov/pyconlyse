import React, { useEffect, useState } from 'react';
import { ACQ_TIMING, readBankField, formatDisplay } from './elyseLiveProjection';
import './SynchronizationEditor.css';

const SUPERVISION = ['LASER/HF', 'IMAC', 'LASER', 'Oscilloscope 1', 'Oscilloscope 2', 'Détection 1', 'Détection 2', 'Machine'];

export default function SynchronizationEditor({ telemetry, client }) {
  const readings = Array.from({ length: 33 }, (_, index) => readBankField(telemetry.payload, 'C1011NI6602', index,
    'number', telemetry.elapsed, telemetry.failure));
  const [draft, setDraft] = useState(Array(33).fill(''));
  const [revision, setRevision] = useState(0);
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const persistent = typeof client?.saveSynchronizationDraft === 'function';
  useEffect(() => {
    const abort = new AbortController();
    if (typeof client?.synchronizationDraft !== 'function') { setLoaded(true); return () => abort.abort(); }
    client.synchronizationDraft(abort.signal).then((result) => {
      if (abort.signal.aborted) return;
      if (!Number.isSafeInteger(result.revision) || result.hardware_applied !== false) throw new Error('Contrat brouillon invalide');
      setRevision(result.revision);
      if (Array.isArray(result.values) && result.values.length === 33 && result.values.every((v) => typeof v === 'number' && Number.isFinite(v))) {
        setDraft(result.values.map(String)); setMessage('Brouillon restauré depuis SQLite · non appliqué au matériel.');
      }
      setLoaded(true);
    }).catch((error) => { if (!abort.signal.aborted) { setMessage(error.message); setLoaded(false); } });
    return () => abort.abort();
  }, [client]);
  const copy = () => {
    if (readings.some((row) => row.quality !== 'FRESH')) { setMessage('Lectures récentes requises ; aucune valeur inconnue remplacée par zéro.'); return; }
    setDraft(readings.map((row) => String(row.value)));
    setMessage('Lectures copiées dans le brouillon · aucune écriture matérielle.');
  };
  const save = async () => {
    if (draft.some((value) => !value.trim() || !Number.isFinite(Number(value)))) { setMessage('33 valeurs numériques explicites sont requises.'); return; }
    setPending(true);
    try {
      const result = await client.saveSynchronizationDraft(draft.map(Number), revision);
      setRevision(result.revision); setMessage('Brouillon enregistré dans SQLite · aucune consigne appliquée à ACQ.');
    } catch (error) { setMessage(error.message); }
    finally { setPending(false); }
  };
  const field = (index, label, writable) => <div className="sup-sync__field" key={index}>
    <span>{label}</span><output aria-label={`${label} · lecture`}>{formatDisplay(readings[index].value)}</output><span>µs</span>
    {writable && <input type="number" step="any" aria-label={`${label} · brouillon`} value={draft[index]}
      disabled={pending} placeholder="Brouillon" onChange={(event) => setDraft((values) => values.map((value, i) => i === index ? event.target.value : value))} />}
  </div>;
  return <section className="sup-sync" aria-label="Synchronisation · lectures et brouillon persistant">
    <div className="sup-sync__actions"><button type="button" onClick={copy} disabled={pending}>Copier lectures ACQ</button>
      <button type="button" onClick={save} disabled={pending || !loaded || !persistent}>Enregistrer brouillon Synchro</button>
      <button type="button" disabled title="Le serveur XP actuel expose uniquement GET ; les écritures distantes sont désactivées.">Appliquer à ACQ</button></div>
    {message && <p role="status">{message}</p>}
    <div className="sup-sync__columns"><fieldset><legend>PC Acquisition · NI6602</legend>
      {ACQ_TIMING.map((rule) => field(rule.index, rule.label, true))}</fieldset>
      <fieldset><legend>PC Supervision · copie ACQ</legend>
        {SUPERVISION.flatMap((name, i) => ['Délais', 'Largeur'].map((kind, j) => field(16 + i * 2 + j, `${kind} ${name}`, false)))}
      </fieldset></div>
  </section>;
}
