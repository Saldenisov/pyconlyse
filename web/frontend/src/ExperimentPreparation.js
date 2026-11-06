import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchWithHardwareApproval } from './api/csrfRequest';
import VD2PrepareChoice from './components/VD2PrepareChoice';
import './css/ExperimentPreparation.css';

const EXPERIMENTS = {
  V0: { controlPath: '/pump-probe-v0' },
  VD2: { controlPath: '/pump-probe-vd2' },
};
const isExperiment = value => Object.prototype.hasOwnProperty.call(EXPERIMENTS, value);
const XENON_SHUTDOWN_NOTICE = 'Xe lamp cooling power (VD2 PDU output 2) is never switched off by Unprepare. Switch the Xe lamp off manually; leave PDU power ON for cooling.';

async function readJson(response, fallback) {
  let payload;
  try {
    payload = await response.json();
  } catch (_error) {
    throw new Error(fallback);
  }
  if (!response.ok || payload.success === false) {
    const failure = new Error(payload.error || payload.recommendation || payload.message || fallback);
    failure.checks = payload.checks || payload.steps || [];
    failure.responseReceived = true;
    failure.job = payload.job;
    throw failure;
  }
  return payload;
}

export async function prepareV0(updateStep) {
  updateStep(0, 'running', 'Confirming and enabling required V0 supplies; STANDA and DG645 timing remain read-only.');
  const response = await fetchWithHardwareApproval('/api/pump-probe-v0/hardware/initialize', {
    method: 'POST', credentials: 'include',
  });
  const result = await readJson(response, 'V0 preparation failed');
  [0, 1, 2].forEach((index) => updateStep(index, 'complete', index === 2
    ? 'DG645 timing checked without changes; acquisition not started.' : 'Required V0 equipment checked.'));
  return result;
}

export async function prepareVD2(updateStep) {
  updateStep(0, 'running', 'Reading the streak-camera equipment state.');
  const stateResponse = await fetch('/api/pump-probe-vd2/state', { credentials: 'include' });
  let initialEquipmentAvailable = false;
  if (stateResponse.ok) {
    const state = await stateResponse.json();
    initialEquipmentAvailable = true;
    updateStep(0, 'complete', `Hamamatsu Tango state: ${state.state || 'available'}.`);
  } else {
    updateStep(0, 'warning', 'Some equipment is unavailable; automatic recovery will be attempted.');
  }

  updateStep(1, 'running', 'Starting PDU servers, confirming power, then checking/reinitializing servers and starting VD2 software.');
  const initializeResponse = await fetchWithHardwareApproval('/api/pump-probe-vd2/initialize', {
    method: 'POST',
    credentials: 'include',
  });
  const preparation = await readJson(initializeResponse, 'VD2 automatic preparation failed');
  if (preparation.already_ready) {
    const message = preparation.message || 'VD2 is already running; all checks passed. No restart or settings change was needed.';
    updateStep(0, 'complete', 'All required VD2 equipment checks passed.');
    updateStep(1, 'complete', 'No restart, power change or settings reset was necessary.');
    updateStep(2, 'complete', message);
    return { checks: preparation.steps || [], alreadyReady: true, message };
  }
  if (!initialEquipmentAvailable) {
    updateStep(0, 'complete', 'Initial equipment availability was restored successfully.');
  }
  updateStep(1, 'complete', 'Required VD2 equipment has been prepared.');

  updateStep(2, 'running', 'Checking RemoteEx and HPD-TA.');
  const runtimeResponse = await fetch('/api/pump-probe-vd2/runtime/state', { credentials: 'include' });
  const runtime = await readJson(runtimeResponse, 'VD2 final verification failed');
  if (!runtime.remoteex_running || !runtime.hpdta_running) {
    updateStep(2, 'error', 'RemoteEx or HPD-TA is not ready.');
    throw new Error('VD2 software did not reach the ready state');
  }
  updateStep(2, 'complete', 'RemoteEx is connected and HPD-TA is running.');
  return { checks: preparation.steps || [] };
}

export async function shutdownVD2(updateStep) {
  updateStep(0, 'running', 'Stopping acquisition, closing shutters and verifying Focus before software closure and power-off.');
  const response = await fetchWithHardwareApproval('/api/pump-probe-vd2/deinitialize', {
    method: 'POST', credentials: 'include',
  });
  const result = await readJson(response, 'VD2 safe shutdown failed');
  updateStep(0, 'complete', 'Acquisition stopped; Focus verified, HPD-TA / RemoteEx closed and SDK ownership released.');
  const warnings = result.warnings || [];
  updateStep(1, warnings.length ? 'warning' : 'complete',
    warnings.length ? warnings.join(' ') : 'VD2 stages stopped without homing; Zaber and shared OWIS supplies retained.');
  updateStep(2, 'complete', 'Flashlamp / camera / trigger supplies verified OFF. Xe lamp cooling power, Zaber power, control supply and unrelated outputs unchanged.');
  return { checks: result.steps || [], message: result.message, warnings };
}

export async function readVD2Lifecycle(experiment = 'VD2') {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 8000);
  let job;
  try {
    const response = await fetch(`/api/pump-probe-${experiment.toLowerCase()}/lifecycle`, {
      credentials: 'include', cache: 'no-store', signal: controller.signal,
    });
    job = (await readJson(response, `Cannot restore ${experiment} preparation state`)).job;
  } finally {clearTimeout(timer);}
  if (!job || !['idle', 'running', 'completed', 'failed', 'interrupted'].includes(job.status)) {
    throw new Error('Invalid preparation snapshot; hardware state is unknown');
  }
  if (job.experiment && job.experiment !== experiment) throw new Error('Wrong experiment snapshot; hardware state is unknown');
  return { ...job, experiment };
}

export async function startVD2Lifecycle(operation, experiment = 'VD2', restoreChoice) {
  const action = operation === 'shutdown' ? 'deinitialize'
    : experiment === 'V0' ? 'hardware/initialize' : 'initialize';
  const response = await fetchWithHardwareApproval(`/api/pump-probe-${experiment.toLowerCase()}/${action}?background=1`, {
    method: 'POST', credentials: 'include',
    ...(restoreChoice ? {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(restoreChoice)} : {}),
  });
  const payload = await readJson(response, `Cannot start ${experiment} operation`);
  if (!payload.job) throw new Error('Backend does not support durable preparation. Update the web server before retrying.');
  return { ...payload.job, experiment };
}

function ShutdownConfirmation({ experiment = 'VD2', onCancel, onConfirm }) {
  const okButton = useRef(null);
  const cancelButton = useRef(null);
  useEffect(() => {
    const previousFocus = document.activeElement;
    okButton.current?.focus();
    return () => { previousFocus?.focus(); };
  }, []);

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onCancel();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      // Holding Enter must not turn one confirmation into repeated requests.
      if (!event.repeat) {
        if (event.target === cancelButton.current) onCancel();
        else onConfirm();
      }
    } else if (event.key === 'Tab') {
      event.preventDefault();
      (document.activeElement === okButton.current ? cancelButton.current : okButton.current)?.focus();
    }
  };

  return createPortal(
    <div className="experiment-confirmation-backdrop">
      <section className="experiment-shutdown-confirmation" role="alertdialog" aria-modal="true"
        aria-labelledby="experiment-shutdown-confirmation-title" aria-describedby="experiment-shutdown-confirmation-description experiment-shutdown-xenon-warning"
        onKeyDown={handleKeyDown}>
        <h2 id="experiment-shutdown-confirmation-title">Unprepare {experiment}?</h2>
        <p id="experiment-shutdown-confirmation-description">Are you sure you want to safely switch off the {experiment} experiment?</p>
        {experiment === 'VD2'
          ? <p>Shutters will close, the streak camera will switch to Focus with verified readback, then HPD-TA / RemoteEx will stop and the flashlamp / camera / trigger supplies will switch off in the verified safe order. Zaber power is never switched off by Unprepare. Shared OWIS power and control supplies remain ON. Tango servers remain running; any active Kymera SDK is deinitialized.</p>
          : <p>Only Andor / UV-vis (SD1 output 1), DG645 (SD2 output 2), Power_current (SD2 output 4) and Power_control (SD2 output 3) will switch off. Acquisition and triggers stop first; V0 TranslationStage1 (OWIS axis 3) then returns to 0 mm with position verification, without homing or redefining coordinates. Andor power is retained until CCD warm-up and SDK release are verified. An unavailable camera server blocks camera power-off and is reported as a failure, not a completed shutdown. Shutdown is blocked while VD2 uses shared supplies. STANDA / Elysium2, other OWIS axes and shared OWIS power remain unchanged; Tango servers remain running.</p>}
        <p id="experiment-shutdown-xenon-warning" role="note">{XENON_SHUTDOWN_NOTICE}</p>
        <p className="experiment-confirmation-hint">Click OK or press Enter to begin. Cancel or Escape leaves equipment unchanged.</p>
        <div className="experiment-confirmation-actions">
          <button ref={cancelButton} type="button" className="experiment-confirmation-cancel" onClick={onCancel}>Cancel</button>
          <button ref={okButton} type="button" className="experiment-shutdown-button" onClick={onConfirm}>OK</button>
        </div>
      </section>
    </div>, document.body
  );
}

const ExperimentPreparation = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = String(searchParams.get('experiment') || 'V0').toUpperCase();
  const [experiment, setExperiment] = useState(isExperiment(requested) ? requested : 'V0');
  const [job, setJob] = useState(null);
  const [restoring, setRestoring] = useState(true);
  const [available, setAvailable] = useState(false);
  const [starting, setStarting] = useState('');
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [restored, setRestored] = useState(false);
  const [clock, setClock] = useState({ server: 0, client: 0 });
  const [now, setNow] = useState(Date.now());
  const [shutdownConfirmation, setShutdownConfirmation] = useState(false);
  const [prepareChoice, setPrepareChoice] = useState(false);
  const requestActive = useRef(false);
  const latestJob = useRef(null);
  const autoStarted = useRef(false);
  const running = Boolean(starting) || job?.status === 'running';
  const operation = starting || job?.operation || 'prepare';
  const locked = restoring || running || shutdownConfirmation || prepareChoice || !available;

  const applyJob = useCallback((next, fromPoll = false) => {
    const previous = latestJob.current;
    latestJob.current = next;
    setConnectionError('');
    if (fromPoll && previous && previous.job_id === next.job_id && previous.status === next.status
        && previous.updated_at === next.updated_at && previous.phase === next.phase) return;

    setJob(next);
    setError(next.error || (['failed', 'interrupted'].includes(next.status)
      ? 'Operation did not complete; equipment state is not verified.' : ''));
    if (next.status === 'running') {
      setRestored(false);
      setPrepareChoice(false);
      setShutdownConfirmation(false);
    }
    setClock({ server: next.server_time || Date.now() / 1000, client: Date.now() });
    setNow(Date.now());
  }, []);

  useEffect(() => {
    let active = true;
    setRestoring(true);
    setAvailable(false);
    readVD2Lifecycle(experiment).then(next => {
      if (!active) return;
      applyJob(next);
      setAvailable(true);
      setRestored(next.status !== 'idle' && next.status !== 'running');
      if (next.status !== 'idle') autoStarted.current = true;
    }).catch(failure => {
      if (!active) return;
      setConnectionError(`${failure.message}. Controls remain locked until the backend state is available.`);
      autoStarted.current = true;
    }).finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, [applyJob, experiment]);

  useEffect(() => {
    if (restoring || starting) return undefined;
    let active = true;
    let timer;
    const poll = async () => {
      try {
        const next = await readVD2Lifecycle(experiment);
        if (active && !requestActive.current) {
          applyJob(next, true);
          setAvailable(true);
        }
      } catch (failure) {
        if (active && !requestActive.current) {
          setAvailable(false);
          setPrepareChoice(false);
          setShutdownConfirmation(false);
          setConnectionError(`${failure.message}. Reconnecting without restarting hardware.`);
        }
      }
      if (active) timer = setTimeout(poll, 1000);
    };
    timer = setTimeout(poll, 1000);
    return () => { active = false; clearTimeout(timer); };
  }, [applyJob, experiment, restoring, starting]);

  useEffect(() => {
    if (!job?.wait_until || !running) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [job?.wait_until, running]);

  const run = useCallback(async (action, restoreChoice) => {
    if (requestActive.current || !available || latestJob.current?.status === 'running') return;
    requestActive.current = true;
    setStarting(action);
    setError('');
    setConnectionError('');
    setRestored(false);
    try {
      applyJob(await startVD2Lifecycle(action, experiment, restoreChoice));
    } catch (failure) {
      if(failure.job?.status==='running'&&(!failure.job.experiment||failure.job.experiment===experiment)) {
        applyJob({...failure.job,experiment});
        setError(failure.message);
        return;
      }
      setError(failure.message || 'Operation failed');
      // A lost POST response does not mean the background job failed to start.
      // Reconcile by GET before allowing another command; never replay the POST.
      if (!failure.responseReceived) {
        setAvailable(false);
        setConnectionError(`${failure.message}. Operation response unavailable. Reading saved progress without repeating the command.`);
      }
    } finally {
      requestActive.current = false;
      setStarting('');
    }
  }, [applyJob, available, experiment]);

  useEffect(() => {
    if (restoring || !available || running || searchParams.get('autostart') !== '1' || autoStarted.current) return;
    autoStarted.current = true;
    if (experiment === 'VD2') setPrepareChoice(true);
    else run('prepare');
  }, [available, restoring, run, running, searchParams, experiment]);

  const selectExperiment = next => {
    if (!isExperiment(next) || locked) return;
    latestJob.current = null;
    setExperiment(next);
    setJob(null);
    setError('');
    setConnectionError('');
    setRestored(false);
    setRestoring(true);
    setAvailable(false);
    setSearchParams({ experiment: next });
  };
  const remaining = Math.max(0, Math.ceil((job?.wait_until || 0) - clock.server - (now - clock.client) / 1000));
  const warnings = job?.result?.warnings || [];
  const message = connectionError || error || (restoring ? 'Reading saved operation…'
    : starting ? `${starting === 'shutdown' ? 'Starting safe shutdown' : 'Checking equipment'}…`
    : job?.status === 'running' ? job.phase || 'Checking equipment…'
    : job?.status === 'completed' ? [job.result?.message || job.phase || 'Operation completed.', ...warnings].join(' ')
    : 'Ready. Select Prepare or Unprepare.');
  const failed = Boolean(connectionError || error);
  const historical = restored && job?.status !== 'running' && !restoring;

  return (
    <main className="experiment-preparation-page">
      <section className="experiment-preparation-shell" aria-label="Experiment preparation">
        <header className="experiment-preparation-header">
          <h1>Prepare experiment</h1>
          <label className="experiment-preparation-selector">Experiment
            <select aria-label="Experiment" value={experiment} disabled={locked} onChange={event => selectExperiment(event.target.value)}>
              <option value="V0">V0</option><option value="VD2">VD2</option>
            </select>
          </label>
        </header>
        <div className="experiment-preparation-actions">
          <button type="button" className="experiment-prepare-button" disabled={locked} onClick={() => experiment === 'VD2' ? setPrepareChoice(true) : run('prepare')}>
            {running && operation === 'prepare' ? `Preparing ${experiment}...` : `Prepare ${experiment}`}
          </button>
          <button type="button" className="experiment-shutdown-button" disabled={locked}
            onClick={() => experiment === 'V0' ? setShutdownConfirmation(true) : run('shutdown')}>
            {running && operation === 'shutdown' ? `Unpreparing ${experiment}...` : `Unprepare ${experiment}`}
          </button>
          <Link className="experiment-control-link" to={EXPERIMENTS[experiment].controlPath + (experiment === 'VD2' && job?.status === 'completed' && job.result?.restored
            ? `?tab=${job.result.restored.ui?.tab === 'alignment' ? 'alignment' : 'acquisition'}&restore_job=${encodeURIComponent(job.job_id)}` : '')}>Open {experiment} controls</Link>
        </div>
        <p className={`experiment-current-action${failed ? ' is-error' : warnings.length ? ' is-warning' : ''}`}
          role={failed ? 'alert' : 'status'} aria-live="polite" aria-atomic="true">
          {historical && <span className="experiment-history-label">Last operation · </span>}{message}
          {running && job?.wait_until && !failed ? <span role="timer" aria-label="Power-up wait"> · {remaining > 0 ? `${remaining} s remaining` : 'Checking power-up completion…'}</span> : null}
        </p>
      </section>
      {shutdownConfirmation && <ShutdownConfirmation experiment={experiment} onCancel={() => setShutdownConfirmation(false)}
        onConfirm={() => { setShutdownConfirmation(false); run('shutdown'); }} />}
      {prepareChoice && <VD2PrepareChoice onCancel={() => setPrepareChoice(false)}
        onConfirm={choice => {setPrepareChoice(false); run('prepare', choice);}} />}
    </main>
  );
};

export default ExperimentPreparation;
