import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import VD2ServerActions from './VD2ServerActions';
import './VD2TranslationStages.css';

const API = '/api/pump-probe-vd2/stages/state';
const ZABER = 'manip/VD2/Zaber';
const OWIS = 'manip/general/DS_OWIS_PS90_IP';
const SAMPLE_AXIS = 2;
const ZABER_OUT_MM = 0;
const ZABER_IN_MM = 50;
const ZABER_PRESET_TOLERANCE_MM = 0.05;

async function jsonResponse(response, fallback) {
  let payload;
  try {
    payload = await response.json();
  } catch (_error) {
    payload = null;
  }
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.error || payload?.message || `${fallback} (HTTP ${response.status})`);
  }
  return payload;
}

function useStageReadings() {
  const [stages, setStages] = useState(null);
  const [error, setError] = useState('');
  const active = useRef(false);
  const loading = useRef(false);

  const refresh = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    try {
      const response = await fetch(API, { credentials: 'include' });
      const payload = await jsonResponse(response, 'Could not read translation stages');
      if (active.current) {
        setStages(payload);
        setError('');
      }
    } catch (cause) {
      if (active.current) setError(cause.message);
    } finally {
      loading.current = false;
    }
  }, []);

  useEffect(() => {
    active.current = true;
    refresh();
    const timer = window.setInterval(refresh, 2500);
    return () => {
      active.current = false;
      window.clearInterval(timer);
    };
  }, [refresh]);

  return { stages, error, refresh };
}

async function command(device, name, args) {
  const response = await fetchWithHardwareApproval(
    `/api/device/${device}/command/${name}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ args }),
    }
  );
  return jsonResponse(response, `Could not run ${name}`);
}

function validTarget(value, stage) {
  if (String(value).trim() === '') throw new Error('Enter a target in millimetres.');
  const millimetres = Number(value);
  if (!Number.isFinite(millimetres)) throw new Error('Target must be a finite number of millimetres.');
  if (Number.isFinite(stage.minimum_mm) && millimetres < stage.minimum_mm) {
    throw new Error(`Target is below ${stage.minimum_mm} mm.`);
  }
  if (Number.isFinite(stage.maximum_mm) && millimetres > stage.maximum_mm) {
    throw new Error(`Target is above ${stage.maximum_mm} mm.`);
  }
  return millimetres;
}

function Position({ value }) {
  return <strong>{Number.isFinite(value) ? `${value.toFixed(4)} mm` : 'Unavailable'}</strong>;
}

function ZaberControl({ stage, refresh }) {
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ready = stage?.state === 'ON';
  const moving = stage?.state === 'MOVING';
  const position = stage?.position_mm;
  const atOut = ready && Number.isFinite(position) && Math.abs(position - ZABER_OUT_MM) <= ZABER_PRESET_TOLERANCE_MM;
  const atIn = ready && Number.isFinite(position) && Math.abs(position - ZABER_IN_MM) <= ZABER_PRESET_TOLERANCE_MM;

  const send = async (name, args) => {
    setBusy(true);
    setError('');
    try {
      await command(ZABER, name, args);
      await refresh();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  const move = (event) => {
    event.preventDefault();
    try {
      send('MoveAbsoluteMm', validTarget(target, stage));
    } catch (cause) {
      setError(cause.message);
    }
  };

  return (
    <VD2ServerActions className="vd2-translation-stage" ariaLabel="Zaber mirror translation stage"
      label="Zaber mirror" servers={[{ name: 'DS_Zaber/1_Zaber' }]} onRestart={refresh}>
      <h3>Zaber mirror</h3>
      <p>Source-selection mirror. Out selects the flash lamp; In selects the continuous lamp.</p>
      <div className="vd2-stage-readings">
        <span>State: <strong>{stage?.state || 'UNKNOWN'}</strong></span>
        <span>Position: <Position value={stage?.position_mm} /></span>
        <span>Source: <strong>{atOut ? 'Flash lamp · Out' : atIn ? 'Continuous lamp · In' : 'Between presets / unknown'}</strong></span>
        <span>Travel: {Number.isFinite(stage?.minimum_mm) && Number.isFinite(stage?.maximum_mm)
          ? `${stage.minimum_mm.toFixed(3)}–${stage.maximum_mm.toFixed(3)} mm` : 'Unavailable'}</span>
      </div>
      {stage?.status && <p className="vd2-stage-status">{stage.status}</p>}
      {stage?.error && <p className="vd2-stage-error" role="alert">{stage.error}</p>}
      {error && <p className="vd2-stage-error" role="alert">{error}</p>}
      <div className="vd2-zaber-presets" role="group" aria-label="Light source positions">
        <button type="button" className={atOut ? 'is-selected' : ''} aria-pressed={atOut}
          disabled={!ready || busy} onClick={() => send('MoveAbsoluteMm', ZABER_OUT_MM)}>
          <strong>Flash lamp</strong><span>Out · 0 mm</span>
        </button>
        <button type="button" className={atIn ? 'is-selected' : ''} aria-pressed={atIn}
          disabled={!ready || busy} onClick={() => send('MoveAbsoluteMm', ZABER_IN_MM)}>
          <strong>Continuous lamp</strong><span>In · 50 mm</span>
        </button>
      </div>
      <form onSubmit={move} className="vd2-zaber-manual">
        <div className="vd2-zaber-manual-row">
          <label>
            Absolute target (mm)
            <input type="number" step="any" value={target} onChange={(event) => setTarget(event.target.value)}
              min={stage?.minimum_mm ?? undefined} max={stage?.maximum_mm ?? undefined} />
          </label>
          <button type="submit" disabled={!ready || busy}>Move</button>
        </div>
      </form>
      <div className="vd2-zaber-utility-actions">
        <button type="button" disabled={!moving} onClick={() => send('Stop', null)}>Stop</button>
        <button type="button" disabled={!ready || busy} onClick={() => {
          if (window.confirm('Home the Zaber stage? The mirror will move to its home switch.')) send('Home', null);
        }}>Home</button>
        <button type="button" disabled={moving || busy} onClick={() => send('Reconnect', null)}>Reconnect</button>
      </div>
      <small>After a controller power cycle, use Home before relying on absolute positions.</small>
    </VD2ServerActions>
  );
}

function OwisSampleControl({ stage, refresh, compact = false, disabled = false, readError = '' }) {
  const [target, setTarget] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ready = !disabled && !readError && !stage?.error && stage?.state === 'ON' && stage?.axis_state === 'ON';
  const moving = stage?.axis_state === 'MOVING';

  const move = async (event) => {
    event.preventDefault();
    if (!ready || busy) return;
    try {
      const millimetres = validTarget(target, stage);
      setBusy(true);
      setError('');
      const result = await command(OWIS, 'move_axis', [SAMPLE_AXIS, millimetres]);
      if (String(result.result) !== '0') throw new Error(String(result.result || 'OWIS move failed'));
      await refresh();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setError('');
    try {
      const result = await command(OWIS, 'stop_axis', SAMPLE_AXIS);
      if (String(result.result) !== '0') throw new Error(String(result.result || 'OWIS stop failed'));
      await refresh();
    } catch (cause) {
      setError(cause.message);
    }
  };

  if (compact) {
    const unavailable = Boolean(readError || stage?.error);
    return <form className="vd2-sample-target" aria-label="OWIS target" onSubmit={move}>
      <label htmlFor="vd2-inline-sample-target">Enter OWIS target (mm)</label>
      <input id="vd2-inline-sample-target" type="number" step="any" placeholder="Target"
        value={target} onChange={event => setTarget(event.target.value)}
        min={stage?.minimum_mm ?? undefined} max={stage?.maximum_mm ?? undefined} />
      <div className="vd2-sample-move">
        <button type="submit" disabled={!ready || busy}>Move to Position</button>
        <output aria-label="OWIS current position" title={stage?.axis_state || 'UNKNOWN'}>
          {!unavailable && Number.isFinite(stage?.position_mm) ? `${stage.position_mm.toFixed(4)} mm` : 'Unavailable'}
          {!unavailable && moving ? ' · Moving' : ''}
        </output>
      </div>
      {(readError || stage?.error || error) && <span role="alert" className="vd2-stage-error">{readError || stage?.error || error}</span>}
    </form>;
  }

  const content = <>
      <h3>OWIS sample holder</h3>
      <p>VD2 sample axis {SAMPLE_AXIS} of {OWIS}.</p>
      <div className="vd2-stage-readings">
        <span>Axis state: <strong>{stage?.axis_state || 'UNKNOWN'}</strong></span>
        <span>Position: <Position value={stage?.position_mm} /></span>
        <span>Travel: {Number.isFinite(stage?.minimum_mm) && Number.isFinite(stage?.maximum_mm)
          ? `${stage.minimum_mm.toFixed(3)}–${stage.maximum_mm.toFixed(3)} mm` : 'Unavailable'}</span>
      </div>
      {stage?.error && <p className="vd2-stage-error" role="alert">{stage.error}</p>}
      {error && <p className="vd2-stage-error" role="alert">{error}</p>}
      <form onSubmit={move} className="vd2-stage-actions">
        <label>
          Absolute target (mm)
          <input type="number" step="any" value={target} onChange={(event) => setTarget(event.target.value)}
            min={stage?.minimum_mm ?? undefined} max={stage?.maximum_mm ?? undefined} />
        </label>
        <button type="submit" disabled={!ready || busy}>Move sample</button>
        <button type="button" disabled={!moving} onClick={stop}>Stop sample</button>
      </form>
    </>;
  return <VD2ServerActions className="vd2-translation-stage" ariaLabel="OWIS sample translation stage"
      label="OWIS sample holder" onRestart={refresh} servers={[
        { name: 'DS_OWIS_PS90/2_IP', label: 'OWIS axis controller' },
      ]}>{content}</VD2ServerActions>;
}

export function VD2SampleHolder({ disabled = false }) {
  const { stages, error, refresh } = useStageReadings();
  return <OwisSampleControl stage={stages?.owis_sample} refresh={refresh} compact disabled={disabled} readError={error} />;
}

export default function VD2TranslationStages({ showOwis = true, showHeading = true }) {
  const { stages, error, refresh } = useStageReadings();
  return (
    <section className="vd2-translation-stages" aria-label="VD2 translation stages">
      {showOwis && showHeading && <header><h2>Translation stages</h2><p>Mirror source selection and VD2 sample positioning.</p></header>}
      {error && <p className="vd2-stage-error" role="alert">{error}</p>}
      <div className="vd2-translation-grid">
        <ZaberControl stage={stages?.zaber_mirror} refresh={refresh} />
        {showOwis && <OwisSampleControl stage={stages?.owis_sample} refresh={refresh} />}
      </div>
    </section>
  );
}
