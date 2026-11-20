import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { acknowledgeTopasError, readTopas, sendTopas, TOPAS_DEVICE } from './topasClient';
import './css/TopasControl.css';

const number = value => value != null && value !== '' && Number.isFinite(Number(value)) ? Number(value).toFixed(2) : '—';
const idOf = value => JSON.stringify(value);
const PRESETS_KEY = `topas.wavelengths.${TOPAS_DEVICE}`;
function loadPresets() {
  try {
    const values = JSON.parse(localStorage.getItem(PRESETS_KEY) || '[]');
    return Array.isArray(values) ? values.filter(v => Number.isFinite(v?.wavelength) && v.wavelength > 0 && typeof v.interaction === 'string').slice(0, 20) : [];
  } catch (_) { return []; }
}

function Motor({ motor, disabled, send }) {
  const [units, setUnits] = useState('units');
  const [target, setTarget] = useState('');
  const [dirty, setDirty] = useState(false);
  const observed = units === 'units' ? motor.TargetPositionInUnits : motor.TargetPosition;
  useEffect(() => { if (!dirty) setTarget(String(observed ?? '')); }, [observed, dirty, units]);
  const actual = units === 'units' ? motor.ActualPositionInUnits : motor.ActualPosition;
  return <form className="topas-motor" aria-label={`Motor ${motor.Index} ${motor.Title}`} onSubmit={event => {
    event.preventDefault();
    if (target.trim() && Number.isFinite(Number(target))) {
      send('set_motor_position', [motor.Index, Number(target), units]);
    }
  }}>
    <header><strong>{motor.Index} · {motor.Title}</strong><span>{motor.IsHoming ? 'Homing' : motor.IsFrozen ? 'Frozen' : ''}</span></header>
    <label>Target<input aria-label={`${motor.Title} target`} type="number" step={units === 'steps' ? '1' : 'any'}
      value={target} onChange={event => { setDirty(true); setTarget(event.target.value); }} disabled={disabled || motor.IsFrozen || motor.IsHoming} /></label>
    <div className="topas-motor-actions"><select aria-label={`${motor.Title} units`} value={units} onChange={event => {
      setUnits(event.target.value); setDirty(false);
    }}><option value="units">{motor.UnitName || 'units'}</option><option value="steps">steps</option></select>
      <button disabled={disabled || motor.IsFrozen || motor.IsHoming || !target.trim()} type="submit">Set</button>
      <button type="button" onClick={() => { setDirty(false); setTarget(String(observed ?? '')); }}>Read</button>
    </div>
    <small>Actual {units === 'steps' ? actual : number(actual)} {units === 'steps' ? 'steps' : motor.UnitName}</small>
    {motor.IsLeftSwitchPressed || motor.IsRightSwitchPressed ? <small className="topas-warning">Limit switch active</small> : null}
  </form>;
}

export default function TopasControl() {
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState('');
  const [commandError, setCommandError] = useState('');
  const [awaited, setAwaited] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [sending, setSending] = useState(false);
  const [wavelength, setWavelength] = useState('');
  const [interaction, setInteraction] = useState('*');
  const [dirty, setDirty] = useState(false);
  const [recent, setRecent] = useState([]);
  const [presets, setPresets] = useState(loadPresets);
  const [refresh, setRefresh] = useState(0);
  const active = useRef(true);
  const inFlight = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(timer); }, []);
  useEffect(() => {
    let mounted = true;
    let timer;
    let request;
    const poll = async () => {
      request = new AbortController();
      const timeout = setTimeout(() => request.abort(), 5000);
      try {
        const value = await readTopas(request.signal);
        if (mounted) { setSnapshot({ ...value, clientReceivedAt: Date.now() }); setNow(Date.now()); setError(''); }
      } catch (failure) {
        if (mounted) setError(failure.name === 'AbortError' ? 'TOPAS status request timed out' : failure.message);
      } finally {
        clearTimeout(timeout);
        if (mounted) timer = setTimeout(poll, 1000);
      }
    };
    poll();
    return () => { mounted = false; clearTimeout(timer); request?.abort(); };
  }, [refresh]);
  const data = snapshot?.data;
  const output = data?.output;
  const shutter = data?.shutter;
  const operation = snapshot?.operation;
  useEffect(() => { if (awaited && operation?.id === awaited) setAwaited(null); }, [awaited, operation?.id]);
  const queued = ['queued', 'running'].includes(operation?.status);
  const age = snapshot?.age_s == null ? null : Number(snapshot.age_s) + Math.max(0, now - snapshot.clientReceivedAt) / 1000;
  const fresh = Boolean(snapshot?.fresh && !error && age != null && age <= (snapshot.stale_after_s || 5));
  const pending = Boolean(sending || queued || awaited);
  const tuning = Boolean(output?.IsWavelengthSettingInProgress);
  const authorized = Boolean(data?.authentication?.CallerHasAccess && !data?.authentication?.AuthenticationHardwareFailure);
  const locked = !fresh || pending || !authorized;
  const moveLocked = locked || tuning || output?.IsWaitingForUserAction || snapshot?.outcome_unknown;
  const draftWavelength = dirty ? wavelength : output?.Wavelength > 0 ? String(output.Wavelength) : '';
  const send = async (command, args = []) => {
    if (inFlight.current) return;
    inFlight.current = true; setSending(true); setCommandError('');
    try {
      const result = await sendTopas(command, args);
      if (active.current) {
        setAwaited(result.result);
        setError(''); setRefresh(value => value + 1);
        if (command === 'set_wavelength') setRecent(values => [{ wavelength: args[0], interaction: args[1] || '*' },
          ...values.filter(v => idOf(v) !== idOf({ wavelength: args[0], interaction: args[1] || '*' }))].slice(0, 8));
      }
    } catch (failure) { if (active.current) setCommandError(failure.message); }
    finally { inFlight.current = false; if (active.current) setSending(false); }
  };
  const submit = event => {
    event.preventDefault();
    if (draftWavelength.trim() && Number(draftWavelength) > 0) send('set_wavelength', interaction === '*'
      ? [Number(draftWavelength)] : [Number(draftWavelength), interaction]);
  };
  const failure = commandError || error || snapshot?.read_error || snapshot?.uncertain_operation?.error || (operation?.status === 'failed' ? operation.error : '');
  return <main className="topas-page">
    <header className="topas-title"><div><Link to="/equipment">Equipment</Link><h1>TOPAS <span>{data?.serial_number || 'T21082'}</span></h1></div>
      <div><span className={fresh ? 'topas-connected' : 'topas-warning'}>{fresh ? 'Connected' : snapshot ? 'Stale / unavailable' : 'Connecting…'}</span>
        <button type="button" onClick={() => setRefresh(v => v + 1)}>Refresh</button></div></header>
    <section className="topas-toolbar" aria-label="TOPAS controls">
      <button type="button" className={`topas-shutter ${shutter?.IsShutterOpen ? 'is-open' : ''}`} disabled={locked || (!shutter?.IsShutterOpen && (moveLocked || shutter?.IsInterlockOpen || shutter?.IsShutterTemporarilyClosedDueSafetyReasons))}
        onClick={() => send('set_shutter', [!shutter.IsShutterOpen])}>{!snapshot ? 'Loading shutter…' : !fresh ? 'Shutter unverified' : shutter?.IsShutterOpen ? 'Shutter OPEN · Close' : 'Shutter CLOSED · Open'}</button>
      <form onSubmit={submit}><label>Wavelength<input type="number" step="any" aria-label="Wavelength nm" value={draftWavelength}
        onChange={e => { setDirty(true); setWavelength(e.target.value); }} disabled={moveLocked} /> nm</label>
        <button type="submit" disabled={moveLocked || !draftWavelength.trim() || !(Number(draftWavelength) > 0)}>Set</button>
        <select aria-label="Interaction" value={interaction} onChange={e => setInteraction(e.target.value)} disabled={moveLocked}>
          <option value="*">Auto interaction</option>{(data?.interactions || []).map(v => <option key={v.Type} value={v.Type}>{v.Type} · {number(v.OutputRange.From)}–{number(v.OutputRange.To)} nm</option>)}</select>
      </form>
      <div className="topas-output"><strong>{output?.Interaction || '—'}</strong><span>{!fresh ? 'Readback unavailable' : tuning ? 'Tuning…' : output?.IsWaitingForUserAction ? 'Operator action required' : shutter?.IsShutterTemporarilyClosedDueSafetyReasons ? 'Shutter held closed by TOPAS safety' : 'Idle'}</span>
        {tuning && Number.isFinite(output?.WavelengthSettingCompletionPart) ? <progress max="1" value={output.WavelengthSettingCompletionPart} aria-label="Tuning progress" /> : null}</div>
      <button type="button" onClick={() => send('stop_motors')} disabled={!fresh || pending || !authorized}>Stop all motors</button>
    </section>
    {failure && <div role="alert" className="topas-error">{failure}
      {commandError && <button type="button" onClick={() => setCommandError('')}>Dismiss</button>}
      {(snapshot?.outcome_unknown || operation?.status === 'failed') && <button type="button" disabled={!fresh || pending || tuning || output?.IsWaitingForUserAction || (snapshot?.outcome_unknown && shutter?.IsShutterOpen)} onClick={async () => {
        try { await acknowledgeTopasError(); if (active.current) { setCommandError(''); setRefresh(v => v + 1); } }
        catch (failure) { if (active.current) setCommandError(failure.message); }
      }}>Acknowledge error · no retry</button>}</div>}
    <div className="topas-workspace">
      <aside className="topas-info"><h2>{fresh ? 'Output info' : 'Last known output'}</h2><dl><dt>Output</dt><dd>{number(output?.Wavelength)} nm</dd>
        <dt>Signal</dt><dd>{number(output?.SignalWavelength)} nm</dd><dt>Idler</dt><dd>{number(output?.IdlerWavelength)} nm</dd>
        <dt>Interaction</dt><dd>{output?.Interaction || '—'}</dd><dt>Calibration</dt><dd>{output ? output.IsWavelengthStrict ? 'Matched' : 'Motors adjusted' : '—'}</dd>
        <dt>Interlock</dt><dd>{!fresh ? 'Unknown' : shutter?.IsInterlockOpen ? 'Open' : 'Closed'}</dd></dl>
        <h2>Saved wavelengths</h2><button type="button" disabled={!fresh || tuning || !(output?.Wavelength > 0)} onClick={() => {
          const value = { wavelength: Number(output.Wavelength), interaction: output.Interaction };
          const next = [value, ...presets.filter(v => idOf(v) !== idOf(value))].slice(0, 20);
          try { localStorage.setItem(PRESETS_KEY, JSON.stringify(next)); setPresets(next); }
          catch (_) { setCommandError('Cannot save wavelengths in this browser'); }
        }}>Save current wavelength</button>
        {presets.map(v => <button type="button" key={idOf(v)} onClick={() => { setDirty(true); setWavelength(String(v.wavelength)); setInteraction(v.interaction); }}>{number(v.wavelength)} nm · {v.interaction}</button>)}
        <h2>Recent requests</h2>{recent.length ? recent.map(v => <button type="button" key={idOf(v)} onClick={() => { setDirty(true); setWavelength(String(v.wavelength)); setInteraction(v.interaction); }}>{number(v.wavelength)} nm · {v.interaction}</button>) : <p>No requests this session</p>}
      </aside>
      <section className="topas-messages"><h2>Messages</h2>{(output?.Messages || []).length ? output.Messages.map((v, i) => <p key={i} className={v.IsCritical ? 'topas-error' : ''}>{v.Text}</p>) : <p>No operator messages</p>}
        {output?.IsWaitingForUserAction && <button type="button" disabled={locked || snapshot?.outcome_unknown} onClick={() => send('confirm_user_actions')}>Confirm actions completed · keep shutter closed</button>}
        <div role="status">{operation ? `${operation.command} · ${operation.status}${operation.status === 'accepted' ? ' · follow readback for completion' : ''}` : 'No pending command'}</div>
        <small>{TOPAS_DEVICE} · {age == null ? 'No telemetry' : `${age.toFixed(1)} s old`}</small>
      </section>
      <section className="topas-motors"><h2>Motors</h2><div>{(data?.motors || []).map(v => <Motor key={v.Index} motor={v} disabled={moveLocked} send={send} />)}</div></section>
    </div>
  </main>;
}
