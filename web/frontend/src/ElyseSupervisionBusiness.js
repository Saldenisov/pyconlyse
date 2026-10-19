import React, { useEffect, useRef, useState } from 'react';

function newIntentId() {
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return `web-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}

function displayNumber(value) {
  // Display only: preserve the original double in intent/ACQ compare-and-write.
  return typeof value === 'number' && Number.isFinite(value) ? Number(value.toPrecision(12)).toString() : value;
}

export default function ElyseSupervisionBusiness({ client, onStatus }) {
  const [snapshot, setSnapshot] = useState(null);
  const [page, setPage] = useState('');
  const [control, setControl] = useState('');
  const [selected, setSelected] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [seeds, setSeeds] = useState({});
  const [selectedTrace, setSelectedTrace] = useState(null);
  const [confirmStop, setConfirmStop] = useState(null);
  const busy = useRef(false);
  const action = useRef(null);
  const mounted = useRef(false);
  const restoredControls = useRef(false);

  useEffect(() => {
    if (!client.business) return undefined;
    mounted.current = true;
    const abort = new AbortController();
    let timer;
    const poll = async () => {
      try {
        const data = await client.business(abort.signal);
        if (!abort.signal.aborted) { setSnapshot(data); setPollError(''); }
      } catch (failure) {
        if (!abort.signal.aborted) { setPollError(failure.message); setSnapshot(null); }
      } finally {
        if (!abort.signal.aborted) timer = setTimeout(poll, 2000);
      }
    };
    poll();
    return () => {
      mounted.current = false; abort.abort(); action.current?.abort(); clearTimeout(timer);
    };
  }, [client]);

  useEffect(() => { onStatus?.(snapshot?.acq || null); }, [snapshot, onStatus]);
  useEffect(() => {
    if (!snapshot || restoredControls.current) return;
    restoredControls.current = true;
    const latest = snapshot.intents[0];
    const command = snapshot.catalog.find((entry) => entry.page === latest?.request.page
      && entry.control === latest?.request.control);
    if (!command) return;
    setPage(command.page); setControl(command.control); setSelected(latest.intent_id);
    if (command.kind === 'SETPOINT' && typeof latest.request.base_value === 'number'
      && Number.isFinite(latest.request.base_value)) {
      setSeeds((previous) => ({ ...previous, [command.target]: String(latest.request.base_value) }));
    }
  }, [snapshot]);

  const entries = snapshot?.catalog || [];
  const pages = [...new Set(entries.map((entry) => entry.page))];
  const currentPage = pages.includes(page) ? page : pages[0] || '';
  const controls = entries.filter((entry) => entry.page === currentPage);
  const currentControl = controls.find((entry) => entry.control === control) || controls[0];
  const intent = snapshot?.intents.find((item) => item.intent_id === selected) || snapshot?.intents[0];
  const isSetpoint = currentControl?.kind === 'SETPOINT';
  const serverValue = snapshot?.acq.setpoints?.[currentControl?.target];
  const initialized = typeof serverValue === 'number' && Number.isFinite(serverValue);
  const seed = seeds[currentControl?.target] ?? '';
  const baseValue = initialized ? serverValue : seed.trim() !== '' ? Number(seed) : NaN;
  const stageAllowed = !!currentControl && (!isSetpoint || Number.isFinite(baseValue));
  const intentSubmissionAllowed = intent?.plan.kind === 'SETPOINT'
    ? snapshot?.setpoint_submission_allowed : snapshot?.submission_allowed;
  const cycle = snapshot?.acq.lifecycle;
  const submitSelected = () => {
    if (intent?.plan.procedure === 'acq.stop') { setConfirmStop(intent.intent_id); return; }
    run((signal) => client.submitIntent(intent.intent_id, snapshot.acq.revision, signal));
  };
  const tracedIntentId = intent?.intent_id;
  const tracedState = intent?.state;
  const acqRevision = snapshot?.acq.revision;
  useEffect(() => {
    setSelectedTrace(null);
    if (!client.intentTrace || !tracedIntentId || ['DRAFT', 'BLOCKED'].includes(tracedState)) return undefined;
    const abort = new AbortController();
    client.intentTrace(tracedIntentId, abort.signal).then((data) => {
      if (!abort.signal.aborted && data.intent_id === tracedIntentId) setSelectedTrace(data);
    }).catch((failure) => {
      if (!abort.signal.aborted) setSelectedTrace({ intent_id: tracedIntentId, phases: [], error: failure.message });
    });
    return () => abort.abort();
  }, [client, tracedIntentId, tracedState, acqRevision]);
  const trace = selectedTrace || (client.intentTrace && tracedIntentId !== snapshot?.acq.trace_intent_id
    ? { intent_id: tracedIntentId, phases: [], error: '' }
    : { intent_id: snapshot?.acq.trace_intent_id, phases: snapshot?.acq.phases, error: snapshot?.acq.trace_error });
  const run = async (callback) => {
    if (busy.current) return;
    busy.current = true; setPending(true); setError('');
    const abort = new AbortController(); action.current = abort;
    try {
      const result = await callback(abort.signal);
      if (!abort.signal.aborted) setSelected(result.intent.intent_id);
    } catch (failure) {
      if (!abort.signal.aborted) setError(failure.message);
    } finally {
      // Read-only reconciliation, never an automatic submission retry.
      if (!abort.signal.aborted) {
        try {
          const data = await client.business(abort.signal);
          if (!abort.signal.aborted) setSnapshot(data);
        } catch (failure) {
          if (!abort.signal.aborted) { setError(failure.message); setSnapshot(null); }
        }
      }
      busy.current = false;
      if (mounted.current) setPending(false);
    }
  };

  if (!client.business) return <p>Client de supervision métier indisponible.</p>;
  return <div className="elyse-business">
    <h2>Supervision métier · ACQ externe</h2>
    <p>ACQ : {snapshot?.acq.mode || 'UNAVAILABLE'} · {snapshot?.acq.quality || 'UNAVAILABLE'}</p>
    {snapshot?.acq.endpoint && <p>Transport backend : {snapshot.acq.endpoint}</p>}
    {cycle && <section aria-label="Cycle ACQ simulé">
      <strong>Cycle ACQ simulé : {cycle.state}</strong>
      <p>{cycle.phase || 'Aucun cycle explicite lancé.'}</p>
      {cycle.error && <p role="status">{cycle.error}</p>}
      {cycle.state === 'UNMANAGED' && <p>Mode précédent conservé : aucune initialisation native déduite des procédures.</p>}
      <p>Initialiser applique les constantes de démarrage, dont Canon 21 et HT 6.5.
        Arrêt général suit sept phases distinctes de shutdown ; nettoyage ne signifie pas sorties nulles.</p>
    </section>}
    {snapshot?.acq.lifecycle_error && <p role="status">{snapshot.acq.lifecycle_error}</p>}
    <p>Intentions et journal restaurés côté serveur. Aucune séquence DAQ dans le navigateur.
      Transmission matérielle désactivée ; seules les réponses simulées sont qualifiées.</p>
    {snapshot?.acq.error && <p role="status">{snapshot.acq.error}</p>}
    {error && <p role="alert">{error}</p>}
    {pollError && <p role="alert">{pollError}</p>}
    <div className="elyse-business__controls">
      <label>Page métier<select value={currentPage} disabled={pending || !snapshot}
        onChange={(event) => { setPage(event.target.value); setControl(''); }}>
        {pages.map((name) => <option key={name}>{name}</option>)}
      </select></label>
      <label>Commande métier<select value={currentControl?.control || ''} disabled={pending || !snapshot}
        onChange={(event) => setControl(event.target.value)}>
        {controls.map((entry) => <option key={entry.control}>{entry.control}</option>)}
      </select></label>
      {isSetpoint && <label>{currentControl.numeric_field} · {initialized ? 'valeur simulée ACQ' : 'valeur initiale simulée'}
        <input type="number" step="any" aria-label={initialized ? 'Valeur simulée ACQ' : 'Valeur initiale simulée'}
          value={initialized ? displayNumber(serverValue) : seed} readOnly={initialized} disabled={pending || !snapshot}
          onChange={(event) => setSeeds((previous) => ({ ...previous, [currentControl.target]: event.target.value }))} />
      </label>}
      <button type="button" disabled={pending || !stageAllowed}
        onClick={() => run((signal) => client.stageIntent({ intent_id: newIntentId(), page: currentPage,
          control: currentControl.control, ...(isSetpoint ? { base_value: baseValue } : {}) }, signal))}>Enregistrer intention</button>
    </div>
    {currentControl?.blocked_reason && <p>{currentControl.blocked_reason}</p>}
    {isSetpoint && <p>Unités logiques natives, pas des volts mesurés. {initialized
      ? 'Base restaurée depuis ACQ ; une intention périmée est refusée.' : 'Premier réglage : fournir une base explicite, aucun zéro supposé.'}
      {currentControl.native_limits && ` Bornes du calcul natif : [${currentControl.native_limits.join(', ')}], pas des limites physiques qualifiées.`}</p>}
    {isSetpoint && snapshot?.acq.setpoint_error && <p role="status">{snapshot.acq.setpoint_error}</p>}
    {isSetpoint && <p>Réglage simulé : {snapshot?.setpoint_submission_allowed ? 'DISPONIBLE, même pendant une procédure' : 'NON QUALIFIÉ / RÉSULTAT NON RÉSOLU'}.</p>}
    <p>Garde : {snapshot?.busy ? 'OCCUPÉ / RÉSULTAT NON RÉSOLU' : snapshot?.submission_allowed ? 'SIMULATION DISPONIBLE' : 'ACQ NON QUALIFIÉ'}.
      Reprise automatique : NON.</p>
    {intent && <section aria-label="Intention sélectionnée">
      <strong>{intent.request.control} · {intent.state}</strong>
      <p>{intent.error || 'Intention enregistrée, sans preuve d’état physique.'}</p>
      {intent.plan.kind === 'SETPOINT' && <p>Base explicite : {displayNumber(intent.request.base_value) ?? 'non fournie'} ·
        Consigne calculée (simulation) : {displayNumber(intent.plan.requested_value) ?? 'non calculée'}</p>}
      <button type="button" disabled={pending || !intentSubmissionAllowed || !!intent.plan.blocked_reason
        || !['DRAFT', 'BLOCKED'].includes(intent.state)}
        onClick={submitSelected}>
        Soumettre à ACQ simulée</button>
    </section>}
    {confirmStop && confirmStop === intent?.intent_id && <div role="dialog" aria-modal="true"
      aria-labelledby="elyse-stop-confirm-title" aria-describedby="elyse-stop-confirm-description"
      onKeyDown={(event) => { if (event.key === 'Escape') setConfirmStop(null); }}>
      <h3 id="elyse-stop-confirm-title">Confirmer l’arrêt général ACQ simulé ?</h3>
      <p id="elyse-stop-confirm-description">Les sept phases et la fermeture seront journalisées.
        Aucun arrêt physique n’est garanti. Entrée confirme, Échap annule.</p>
      <form onSubmit={(event) => {
        event.preventDefault();
        if (pending || !intentSubmissionAllowed || !['DRAFT', 'BLOCKED'].includes(intent.state)) return;
        setConfirmStop(null);
        run((signal) => client.submitIntent(confirmStop, snapshot.acq.revision, signal));
      }}>
        <button type="submit" autoFocus disabled={pending || !intentSubmissionAllowed}>Confirmer l’arrêt simulé</button>
        <button type="button" onClick={() => setConfirmStop(null)}>Annuler</button>
      </form>
    </div>}
    <h3>Intentions persistantes</h3>
    <ul>{snapshot?.intents.map((item) => <li key={item.intent_id}>
      <button type="button" onClick={() => { setSelected(item.intent_id); setPage(item.request.page);
        setControl(item.request.control); }}>{item.request.control} · {item.state}</button>
      <small> {item.updated_at}</small>
    </li>)}</ul>
    <details><summary>Journal métier persistant</summary><ol>{snapshot?.events.map((event) =>
      <li key={event.seq}>{event.recorded_at} · {event.intent_id} · {event.state} · {event.message}</li>)}</ol></details>
    <details><summary>Journal ACQ · phases simulées</summary>
      <p>{trace.intent_id || 'Aucune intention transmise'}</p>
      {trace.error && <p role="status">{trace.error}</p>}
      <ol>{trace.phases?.map((phase, index) => <li key={index}>
        {phase.recorded_at} · {phase.step_index} · {phase.operation} · {phase.outcome}
        {phase.detail.label && ` · ${phase.detail.label}`}
        {phase.operation === 'setpoint' && phase.outcome === 'SUCCEEDED'
          && ` · ${phase.detail.control} : ${displayNumber(phase.detail.base_value)} → ${displayNumber(phase.detail.value)}`}
        {phase.detail.error && ` · ${phase.detail.error}`}
      </li>)}</ol>
    </details>
  </div>;
}
