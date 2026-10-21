import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import './AcquisitionCommands.css';

const Context = createContext(null);
const id = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (x) => x.toString(16).padStart(2, '0')).join('');

export function useAcquisitionPanelName(name) {
  const control = useContext(Context);
  return `${name} · ${control?.view?.source_selected && control?.fresh ? 'commandes supervisées' : 'lecture seule'}`;
}

export function AcquisitionCommand({ operation, name, className, children }) {
  const control = useContext(Context);
  const capability = control?.view?.capabilities?.[operation];
  const enabled = !!(operation && capability?.enabled && control?.fresh && !control?.pending);
  return <button type="button" disabled={!enabled} className={className}
    aria-label={enabled ? name.replace(/ · (commande )?désactivée?$/, '') : name}
    title={enabled ? 'Commande via Tango → Acquisition Python. Confirmation obligatoire.'
      : capability?.reason || 'Commande non disponible sur le serveur Python sélectionné.'}
    onClick={() => control.choose(operation, name.replace(/ · (commande )?désactivée?$/, ''))}>{children}</button>;
}

export default function AcquisitionCommands({ client, children }) {
  const [view, setView] = useState(null), [fresh, setFresh] = useState(false);
  const [pending, setPending] = useState(false), [confirmation, setConfirmation] = useState(null);
  const [message, setMessage] = useState(''), [failure, setFailure] = useState('');
  const received = useRef(0), latest = useRef(null), busy = useRef(false), mounted = useRef(true);
  const supported = typeof client?.controlState === 'function' && typeof client?.command === 'function';
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
      } catch (error) {
        if (!abort.signal.aborted) { setFresh(false); setFailure(error.message || 'Contrôle Python indisponible'); }
      } finally { if (!abort.signal.aborted) timer = setTimeout(poll, 1000); }
    };
    poll();
    const age = setInterval(() => { if (performance.now() - received.current >= 2000) setFresh(false); }, 250);
    return () => { mounted.current = false; abort.abort(); clearTimeout(timer); clearInterval(age); };
  }, [client, supported]);
  const choose = (operation, name) => {
    if (busy.current || !fresh || performance.now() - received.current >= 2000
      || latest.current?.capabilities?.[operation]?.enabled !== true) return;
    setConfirmation({ operation, name, session_id: latest.current.session_id, expected_revision: latest.current.revision });
  };
  const execute = async () => {
    const choice = confirmation;
    if (!choice || busy.current) return;
    const current = latest.current;
    setConfirmation(null);
    if (!fresh || performance.now() - received.current >= 2000
      || current?.session_id !== choice.session_id || current?.revision !== choice.expected_revision
      || current?.capabilities?.[choice.operation]?.enabled !== true) {
      setMessage('État Acquisition modifié ou périmé. Relire et confirmer à nouveau.'); return;
    }
    busy.current = true; setPending(true);
    try {
      const result = await client.command({ command_id: id(), session_id: choice.session_id,
        expected_revision: choice.expected_revision, operation: choice.operation, operator_confirmed: true, value: null });
      if (mounted.current) setMessage(`${choice.name} : ${result.receipt.outcome} · vérifier le retour Acquisition.`);
    } catch (error) {
      if (mounted.current) setMessage(`${error.message} · Aucun renvoi automatique. Vérifier le journal Acquisition.`);
    } finally {
      busy.current = false;
      if (mounted.current) { setPending(false); setFresh(false); }
    }
  };
  const last = view?.commands?.[0];
  return <Context.Provider value={{ view, fresh, pending, choose }}>
    {supported && <div className="acq-command-status" aria-label="État commandes Acquisition">
      <span>{failure || (view?.source_selected ? `Acquisition Python : ${view.state}` : 'LabVIEW : lecture seule · commandes Python non activées')}
        {view?.startup_phase && view.startup_phase !== 'NOT_STARTED' ? ` · ${view.startup_phase}` : ''}</span>
      {last && <span>{last.operation} : {last.outcome}{last.error ? ` · ${last.error}` : ''}
        {['QUEUED', 'EXECUTING', 'INDETERMINATE'].includes(last.outcome) ? ' · Ne pas renvoyer la commande.' : ''}</span>}
      {message && <span role="status">{message}</span>}
    </div>}
    {children}
    {confirmation && <div className="acq-command-modal"><section role="dialog" aria-modal="true" aria-label="Confirmer commande Acquisition"
      onKeyDown={(event) => {
        if (event.key === 'Escape') setConfirmation(null);
        if (event.key === 'Tab') {
          const buttons = [...event.currentTarget.querySelectorAll('button')];
          const next = (buttons.indexOf(document.activeElement) + (event.shiftKey ? -1 : 1) + buttons.length) % buttons.length;
          event.preventDefault(); buttons[next].focus();
        }
      }}>
      <h2>{confirmation.name}</h2><p>Exécuter cette commande sur l’équipement réel ?</p>
      {confirmation.operation === 'modulator.general.start' && <p>General → démarrage de l’eau → circulation CANON et SECTION confirmée pendant 2 s. Les étapes suivantes restent bloquées sinon.</p>}
      <p>Une commande acceptée n’est pas une confirmation physique. Aucun renvoi automatique.</p>
      <button type="button" autoFocus onClick={() => setConfirmation(null)}>Annuler</button>
      <button type="button" onClick={execute}>Confirmer</button>
    </section></div>}
  </Context.Provider>;
}
