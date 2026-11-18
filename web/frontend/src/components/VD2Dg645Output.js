import { useEffect, useState } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';

const API = '/api/pump-probe-vd2/dg645/output';

async function readOutput(response) {
  const result = await response.json();
  if (!response.ok || result.success !== true) {
    throw new Error(result.error || 'DG645 Output is unavailable');
  }
  return result;
}

export default function VD2Dg645Output({ disabled, enableBlocked }) {
  const [output, setOutput] = useState(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (pending) return undefined;
    const controller = new AbortController();
    let timer;
    const refresh = async () => {
      try {
        const result = await readOutput(await fetch(API, { signal: controller.signal }));
        if (!controller.signal.aborted) setOutput(result);
      } catch {
        if (!controller.signal.aborted) setOutput(null);
      } finally {
        if (!controller.signal.aborted) timer = window.setTimeout(refresh, 4000);
      }
    };
    refresh();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [pending]);

  const toggle = async enabled => {
    setPending(true);
    setError('');
    try {
      const response = await fetchWithHardwareApproval(API, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      const result = await readOutput(response);
      if (result.enabled !== enabled) throw new Error('DG645 did not confirm Output');
      setOutput(result);
    } catch (cause) {
      setOutput(null);
      setError(cause.message);
    } finally {
      setPending(false);
    }
  };

  const locked = disabled || pending || typeof output?.enabled !== 'boolean';
  return <div className="vd2-dg645-output" role="group" aria-label="DG645 Output">
    <span>DG645 Output</span>
    <button type="button" aria-pressed={output?.enabled === true}
      disabled={locked || enableBlocked || output?.enabled === true} onClick={() => toggle(true)}>On</button>
    <button type="button" aria-pressed={output?.enabled === false}
      disabled={locked || output?.enabled === false} onClick={() => toggle(false)}>Off</button>
    <output aria-live="polite">{pending ? 'Applying…' : !output ? 'Unavailable'
      : output.enabled === null ? 'External or other trigger mode'
      : output.enabled ? `On · ${output.rate_hz} Hz` : 'Standby (Internal)'}</output>
    {error && <small role="alert">{error}</small>}
  </div>;
}
