import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import './AcquisitionCommands.css';
import { CIRCULATION_CONFIRMATION, validCommandValue, sameCommandValue, describeCommandValue } from './acquisitionCommandValue';

const Context = createContext(null);
const id = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (x) => x.toString(16).padStart(2, '0')).join('');
const changedMessage = 'État Acquisition modifié ou périmé. Relire et confirmer à nouveau.';
const capabilityKey = (value) => JSON.stringify(Object.keys(value?.capabilities || {}).sort()
  .map((name) => [name, value.capabilities[name]?.enabled, value.capabilities[name]?.reason || '']));
const currentNative = (value) => value?.source_selected === true
  && (value.source_mode === undefined || value.source_mode === 'PYTHON_NATIVE')
  && /^[0-9a-f]{32}$/.test(value.session_id || '') && Number.isSafeInteger(value.revision) && value.revision >= 0;
const validValue = validCommandValue;
export function circulationConfirmationCandidates(view) {
  const safety = view?.cooling_safety;
  const candidates = safety?.confirmation_candidates;
  if (safety?.confirmation_required !== true || !Array.isArray(candidates)
    || !validValue(CIRCULATION_CONFIRMATION, { incident_ids: candidates.map((item) => item?.incident_id) })
    || candidates.some((item) => !['CANON', 'SECTION'].includes(item?.circuit)
      || typeof item.deadline_utc !== 'string' || !Number.isFinite(Date.parse(item.deadline_utc)))) return [];
  return candidates.map(({ incident_id, circuit, deadline_utc }) => ({ incident_id, circuit, deadline_utc }));
}
const waterKey = (view) => JSON.stringify(circulationConfirmationCandidates(view));
const waterSelectionCurrent = (view, value) => sameCommandValue(CIRCULATION_CONFIRMATION, value,
  { incident_ids: circulationConfirmationCandidates(view).map((item) => item.incident_id) });
const deadlineText = (value) => new Date(value).toLocaleTimeString('fr-FR', {
  timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit', second: '2-digit',
});
export const COMMAND_INTENTS_KEY = 'elyse-acquisition-unresolved-intents-v1';
const TERMINAL = new Set(['COMPLETED', 'FAILED', 'REJECTED', 'INTERRUPTED']);
const emptyLedger = () => ({ schema_version: 1, intents: [], stop_intent: null, error: '' });
const validIntent = (item) => /^[0-9a-f]{32}$/.test(item?.command_id || '')
  && /^[0-9a-f]{32}$/.test(item?.session_id || '') && typeof item.operation === 'string'
  && Number.isSafeInteger(item.expected_revision) && item.expected_revision >= 0 && validValue(item.operation, item.value);
function readLedger() {
  try {
    const raw = window.sessionStorage.getItem(COMMAND_INTENTS_KEY);
    if (raw === null) return emptyLedger();
    const value = JSON.parse(raw);
    if (value?.schema_version !== 1 || !Array.isArray(value.intents) || value.intents.length > 16
      || typeof value.error !== 'string' || value.intents.some((item) => !validIntent(item))
      || (value.stop_intent != null && (!validIntent(value.stop_intent)
        || value.stop_intent.operation !== 'modulator.general.stop'))) throw new Error();
    return { ...value, stop_intent: value.stop_intent || null };
  } catch (_error) { return { ...emptyLedger(), error: 'Historique local illisible : contrôle local requis avant une nouvelle mise en marche.' }; }
}

export function useAcquisitionPanelName(name) {
  const control = useContext(Context);
  return `${name} · ${control?.view?.source_selected && control?.fresh ? 'commandes supervisées' : 'lecture seule'}`;
}

export function useAcquisitionConnection() {
  const control = useContext(Context);
  return { view: control?.view, fresh: control?.fresh === true };
}

export function AcquisitionCommand({ operation, name, value = null, className, children }) {
  const control = useContext(Context);
  const capability = control?.view?.capabilities?.[operation];
  const invalidateValue = control?.invalidateValue;
  useEffect(() => { invalidateValue?.(operation, value); }, [invalidateValue, operation, value]);
  const enabled = !!(operation && capability?.enabled === true && currentNative(control?.view)
    && validValue(operation, value) && control?.fresh && !control?.pending && control?.permitted(operation));
  return <button type="button" disabled={!enabled} className={className}
    aria-label={enabled ? name.replace(/ · (commande )?désactivée?$/, '') : name}
    title={enabled ? 'Commande via Tango → Acquisition Python. Confirmation obligatoire.'
      : !validValue(operation, value) ? (operation === CIRCULATION_CONFIRMATION
        ? 'Les incidents de refroidissement courants doivent être sélectionnés explicitement.' : operation === 'counter_timing.set'
        ? 'Saisir compteur C10, délai et largeur explicites et valides.' : 'Saisir une consigne HT explicite et finie de 0 à 20 kV.')
        : capability?.reason || 'Commande non disponible sur le serveur Python sélectionné.'}
    onClick={() => control.choose(operation, name.replace(/ · (commande )?désactivée?$/, ''), value)}>{children}</button>;
}

export default function AcquisitionCommands({ client, children }) {
  const [view, setView] = useState(null), [fresh, setFresh] = useState(false);
  const [pending, setPending] = useState(false), [confirmation, setConfirmation] = useState(null);
  const [message, setMessage] = useState(''), [failure, setFailure] = useState('');
  const [ledger, setLedger] = useState(readLedger);
  const received = useRef(0), latest = useRef(null), busy = useRef(false), mounted = useRef(true);
  const outstanding = useRef(ledger);
  const selected = useRef(null);
  const supported = typeof client?.controlState === 'function' && typeof client?.command === 'function';
  const saveLedger = useCallback((value) => {
    let stored = value;
    try { window.sessionStorage.setItem(COMMAND_INTENTS_KEY, JSON.stringify(value)); }
    catch (_error) { stored = { ...value, error: 'Historique local non enregistrable : nouvelles mises en marche bloquées.' }; }
    outstanding.current = stored;
    if (mounted.current) setLedger(stored);
    return !stored.error;
  }, []);
  const permitted = (operation) => operation === 'modulator.general.stop' ? !outstanding.current.stop_intent
    : !outstanding.current.error && outstanding.current.intents.length === 0 && !outstanding.current.stop_intent;
  const dismiss = useCallback(() => { selected.current = null; setConfirmation(null); }, []);
  const invalidate = useCallback((reason = changedMessage) => {
    if (selected.current && !selected.current.invalidated) {
      selected.current = { ...selected.current, invalidated: true, invalidationReason: reason };
      setConfirmation(selected.current); setMessage(reason);
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    if (!supported) return undefined;
    const abort = new AbortController();
    let timer;
    const poll = async () => {
      try {
        const value = await client.controlState(abort.signal);
        if (abort.signal.aborted) return;
        latest.current = value; received.current = performance.now();
        setView(value); setFresh(true); setFailure('');
        const unresolved = outstanding.current.intents;
        const resolved = (intent) => value.commands?.some((receipt) =>
          receipt.command_id === intent.command_id && receipt.session_id === intent.session_id
          && receipt.operation === intent.operation && TERMINAL.has(receipt.outcome)
          && receipt.hardware_acknowledged === false && receipt.automatic_retry === false);
        const reconciled = unresolved.filter((intent) => !resolved(intent));
        const priorStop = outstanding.current.stop_intent;
        const stop = priorStop && resolved(priorStop) ? null : priorStop;
        if (reconciled.length !== unresolved.length || stop !== priorStop) {
          saveLedger({ ...outstanding.current, intents: reconciled, stop_intent: stop });
        }
        const choice = selected.current;
        if (choice && (!currentNative(value) || value.session_id !== choice.session_id
          || value.revision !== choice.expected_revision || capabilityKey(value) !== choice.capabilities
          || (choice.operation === CIRCULATION_CONFIRMATION && waterKey(value) !== choice.water_key))) invalidate();
      } catch (error) {
        if (!abort.signal.aborted) {
          setFresh(false); setFailure(error.message || 'Contrôle Python indisponible'); invalidate();
        }
      } finally { if (!abort.signal.aborted) timer = setTimeout(poll, 1000); }
    };
    poll();
    const age = setInterval(() => {
      if (performance.now() - received.current >= 2000) { setFresh(false); invalidate(); }
    }, 250);
    return () => { mounted.current = false; abort.abort(); clearTimeout(timer); clearInterval(age); };
  }, [client, supported, invalidate, saveLedger]);
  const choose = (operation, name, value) => {
    if (busy.current || !fresh || performance.now() - received.current >= 2000
      || !currentNative(latest.current) || !validValue(operation, value) || !permitted(operation)
      || latest.current?.capabilities?.[operation]?.enabled !== true
      || (operation === CIRCULATION_CONFIRMATION && !waterSelectionCurrent(latest.current, value))) return;
    const frozenValue = operation === CIRCULATION_CONFIRMATION
      ? Object.freeze({ incident_ids: Object.freeze([...value.incident_ids]) })
      : value !== null && typeof value === 'object' ? Object.freeze({ ...value }) : value;
    selected.current = { operation, name, value: frozenValue, session_id: latest.current.session_id,
      expected_revision: latest.current.revision, capabilities: capabilityKey(latest.current), invalidated: false,
      ...(operation === CIRCULATION_CONFIRMATION ? { water_key: waterKey(latest.current),
        water_candidates: circulationConfirmationCandidates(latest.current) } : {}) };
    setConfirmation(selected.current);
  };
  const invalidateValue = useCallback((operation, value) => {
    if (selected.current && operation && selected.current.operation === operation
      && !sameCommandValue(operation, selected.current.value, value)) {
      invalidate('Consigne modifiée. Annuler puis confirmer la nouvelle valeur explicitement.');
    }
  }, [invalidate]);
  const execute = async () => {
    const choice = selected.current;
    if (!choice || busy.current) return;
    const current = latest.current;
    dismiss();
    if (choice.invalidated || !fresh || performance.now() - received.current >= 2000 || !currentNative(current) || !permitted(choice.operation)
      || current?.session_id !== choice.session_id || current?.revision !== choice.expected_revision
      || capabilityKey(current) !== choice.capabilities || !validValue(choice.operation, choice.value)
      || current?.capabilities?.[choice.operation]?.enabled !== true
      || (choice.operation === CIRCULATION_CONFIRMATION && (!waterSelectionCurrent(current, choice.value)
        || waterKey(current) !== choice.water_key))) {
      setMessage(changedMessage); return;
    }
    busy.current = true; setPending(true);
    const request = { command_id: id(), session_id: choice.session_id,
      expected_revision: choice.expected_revision, operation: choice.operation, operator_confirmed: true, value: choice.value };
    const protectiveStop = choice.operation === 'modulator.general.stop';
    if (!protectiveStop && outstanding.current.intents.length >= 16) {
      busy.current = false; setPending(false);
      setMessage('Historique local saturé : vérification locale requise. Aucune nouvelle commande envoyée.'); return;
    }
    // One reserved protective-stop slot never discards or grows the normal
    // bounded ledger. A second unresolved stop is not silently replayed.
    const saved = saveLedger(protectiveStop ? { ...outstanding.current, stop_intent: request }
      : { ...outstanding.current, intents: [...outstanding.current.intents, request] });
    if (!saved) {
      busy.current = false; setPending(false);
      setMessage('Intention non enregistrée : aucune commande envoyée. Si un arrêt est nécessaire, utiliser la procédure locale qualifiée.'); return;
    }
    try {
      const result = await client.command(request);
      if (result.receipt.outcome !== 'INDETERMINATE') {
        saveLedger(protectiveStop ? { ...outstanding.current, stop_intent: null }
          : { ...outstanding.current, intents: outstanding.current.intents.filter((item) => item.command_id !== request.command_id) });
      }
      if (mounted.current) setMessage(`${choice.name} : ${result.receipt.outcome}${result.receipt.error ? ` · ${result.receipt.error}` : ''} · vérifier le retour Acquisition.`);
    } catch (error) {
      if (mounted.current) setMessage(`${error.message} · Résultat UNKNOWN. Aucun renvoi automatique. Vérifier le journal Acquisition.`);
    } finally {
      busy.current = false;
      if (mounted.current) { setPending(false); setFresh(false); }
    }
  };
  const last = view?.commands?.[0];
  const waterCandidates = circulationConfirmationCandidates(view);
  const waterValue = { incident_ids: waterCandidates.map((item) => item.incident_id) };
  return <Context.Provider value={{ view, fresh, pending, choose, invalidateValue, permitted }}>
    {supported && <div className="acq-command-status" aria-label="État commandes Acquisition">
      <span>{failure || (view?.source_selected ? `Acquisition Python : ${view.state}`
        : view?.source_mode === 'LABVIEW_BRIDGE' || view?.mode === 'LABVIEW_READ_ONLY'
          ? 'Serveur XP : relais VI · lecture seule · commandes Python non activées'
          : `Serveur XP : ${view?.state || 'en attente'} · commandes non disponibles`)}
        {view?.startup_phase && view.startup_phase !== 'NOT_STARTED' ? ` · ${view.startup_phase}` : ''}</span>
      {last && <span>{last.operation} : {last.outcome}{last.error ? ` · ${last.error}` : ''}
        {['QUEUED', 'EXECUTING', 'INDETERMINATE'].includes(last.outcome) ? ' · Ne pas renvoyer la commande.' : ''}</span>}
      {message && <span role="status">{message}</span>}
      {(ledger.error || ledger.intents.length > 0 || ledger.stop_intent) && <span role="alert">{ledger.error || 'Intention non résolue : nouvelles commandes bloquées, sauf Arrêt General autorisé sans arrêt déjà non résolu.'}
        {ledger.intents.map((intent) => ` · ${intent.operation}${describeCommandValue(intent.operation, intent.value) ? ` = ${describeCommandValue(intent.operation, intent.value)}` : ''} · ${intent.command_id}`).join('')}
        {ledger.stop_intent && ` · Arrêt General non résolu : ${ledger.stop_intent.command_id}. Aucun second envoi ; vérifier localement si un arrêt est nécessaire.`}
        {' '}Un historique vide ou un nouveau démarrage du serveur ne vaut pas réconciliation.</span>}
    </div>}
    {supported && waterCandidates.length > 0 && <section role="alert" aria-label="Confirmer la circulation physique de l’eau" className="acq-command-status">
      <strong>Vérifier la circulation d’eau maintenant</strong>
      <p>Après passage du vert au rouge, l’eau circule-t-elle physiquement dans les circuits suivants ?</p>
      <ul>{waterCandidates.map((item) => <li key={item.incident_id}>{item.circuit} · échéance serveur {deadlineText(item.deadline_utc)}</li>)}</ul>
      <p>Délai serveur : 120 s. Sans confirmation, l’arrêt supplémentaire reste demandé à l’échéance.</p>
      <AcquisitionCommand operation={CIRCULATION_CONFIRMATION} name="Confirmer la circulation physique de l’eau" value={waterValue}>
        L’eau circule physiquement maintenant…
      </AcquisitionCommand>
      <p>Confirmer uniquement après vérification sur place. Aucun reset ni démarrage. Les règles de la garde VI restent inchangées.</p>
    </section>}
    {children}
    {confirmation && <div className="acq-command-modal"><section role="dialog" aria-modal="true" aria-label="Confirmer commande Acquisition"
      onKeyDown={(event) => {
        if (event.key === 'Escape') dismiss();
        if (event.key === 'Tab') {
          const buttons = [...event.currentTarget.querySelectorAll('button:not(:disabled)')];
          const next = (buttons.indexOf(document.activeElement) + (event.shiftKey ? -1 : 1) + buttons.length) % buttons.length;
          event.preventDefault(); buttons[next].focus();
        }
      }}>
      <h2>{confirmation.name}</h2><p>{confirmation.operation === CIRCULATION_CONFIRMATION
        ? 'L’eau circule-t-elle physiquement maintenant dans chacun de ces circuits ?' : 'Exécuter cette commande sur l’équipement réel ?'}</p>
      {confirmation.operation === CIRCULATION_CONFIRMATION && <>
        <ul>{confirmation.water_candidates.map((item) => <li key={item.incident_id}>{item.circuit} · échéance serveur {deadlineText(item.deadline_utc)}</li>)}</ul>
        <p>Oui annule uniquement l’arrêt supplémentaire de 120 s pour ces incidents. Le signal rouge reste affiché. Les règles de la garde VI restent inchangées. Aucun incident futur n’est confirmé.</p>
      </>}
      {confirmation.operation === 'ht_voltage.set' && <p>Consigne confirmée : <strong>{confirmation.value} kV</strong>. Une valeur unique, aucune rampe automatique.</p>}
      {confirmation.operation === 'counter_timing.set' && <p>Réglage confirmé : <strong>{describeCommandValue(confirmation.operation, confirmation.value)}</strong>.
        Le compteur sélectionné sera arrêté, reconfiguré puis redémarré. La commande ne démarre pas un compteur auparavant arrêté.</p>}
      {confirmation.operation === 'modulator.general.start' && <p>{view?.operator_supervised_test
        ? 'General uniquement. Démarrer l’eau séparément, puis vérifier la circulation CANON et SECTION. Aucun autre démarrage automatique.'
        : 'General → démarrage de l’eau → circulation CANON et SECTION confirmée pendant 2 s. Les étapes suivantes restent bloquées sinon.'}</p>}
      {confirmation.invalidated && <p role="alert">{confirmation.invalidationReason}</p>}
      <p>{confirmation.operation === CIRCULATION_CONFIRMATION
        ? 'Cette confirmation est une déclaration de l’opérateur, pas un retour capteur indépendant. Aucun renvoi automatique.'
        : 'Une commande acceptée n’est pas une confirmation physique. Aucun renvoi automatique.'}</p>
      <button type="button" autoFocus onClick={dismiss}>Annuler</button>
      <button type="button" disabled={confirmation.invalidated} onClick={execute}>{confirmation.operation === CIRCULATION_CONFIRMATION
        ? 'Oui, l’eau circule physiquement maintenant' : 'Confirmer'}</button>
    </section></div>}
  </Context.Provider>;
}
