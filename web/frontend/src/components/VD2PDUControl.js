import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import VD2ServerActions from './VD2ServerActions';
import './VD2PDUControl.css';

const PDUS = [
  { label: 'PDU SD2', device: 'manip/SD2/PDU_SD2', server: 'DS_Netio_pdu/4_SD2' },
  { label: 'PDU VD2', device: 'manip/VD2/PDU_VD2', server: 'DS_Netio_pdu/2_VD2' },
];

async function readOutputs(device) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 5000);
  let response;
  try {
    response = await fetch(`/api/device/${device}/pdu/outputs`, {
      credentials: 'include', signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
  const payload = await response.json();
  if (!response.ok || payload.success === false) {
    throw new Error(payload.error || `Could not read ${device}`);
  }
  const outputs = (payload.outputs || []).map((output) => ({
    id: Number(output.id), name: String(output.name), state: Number(output.state),
  }));
  if (!outputs.length || outputs.some((output) => !Number.isInteger(output.id) || ![0, 1].includes(output.state))) {
    throw new Error(`Invalid output state from ${device}`);
  }
  return { state: payload.state || 'UNKNOWN', outputs };
}

export default function VD2PDUControl() {
  const [devices, setDevices] = useState({});
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState({});
  const active = useRef(false);
  const loading = useRef(false);
  const busyDevices = useRef(new Set());

  const refresh = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    try {
      await Promise.all(PDUS.map(async ({ device }) => {
        if (busyDevices.current.has(device)) return;
        try {
          const snapshot = await readOutputs(device);
          if (active.current) {
            setDevices((current) => ({ ...current, [device]: snapshot }));
            setErrors((current) => ({ ...current, [device]: '' }));
          }
        } catch (error) {
          if (active.current) setErrors((current) => ({ ...current, [device]: error.message }));
        }
      }));
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

  const setOutput = async (device, outputId, enabled) => {
    if (busyDevices.current.has(device)) return;
    busyDevices.current.add(device);
    setBusy((current) => ({ ...current, [device]: true }));
    setErrors((current) => ({ ...current, [device]: '' }));
    try {
      // The Tango command writes the entire PDU, so read all outlets again
      // immediately before changing exactly one selected outlet.
      const current = await readOutputs(device);
      const target = current.outputs.find((output) => output.id === outputId);
      if (!target) throw new Error(`Output ${outputId} is missing on ${device}`);
      const requested = current.outputs.map((output) => output.id === outputId ? Number(enabled) : output.state);
      if (target.state !== Number(enabled)) {
        const response = await fetchWithHardwareApproval(`/api/device/${device}/command/set_channels_states`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
          body: JSON.stringify({ args: requested }),
        });
        const payload = await response.json();
        if (!response.ok || payload.success === false) throw new Error(payload.error || `Could not switch output ${outputId}`);
      }
      const observed = await readOutputs(device);
      if (observed.outputs.length !== requested.length ||
          observed.outputs.some((output, index) => output.id !== current.outputs[index].id || output.state !== requested[index])) {
        throw new Error(`Output ${outputId} did not reach the requested state; check ${device}`);
      }
      if (active.current) setDevices((previous) => ({ ...previous, [device]: observed }));
    } catch (error) {
      if (active.current) setErrors((current) => ({ ...current, [device]: error.message }));
    } finally {
      busyDevices.current.delete(device);
      if (active.current) setBusy((current) => ({ ...current, [device]: false }));
    }
  };

  return (
    <div className="vd2-pdu-panel" aria-label="VD2 PDU controls">
      <header><h2>Power distribution</h2><p>SD2 and VD2 outlets. States update automatically.</p>
        <button type="button" onClick={refresh}>Refresh</button></header>
      <div className="vd2-pdu-grid">
        {PDUS.map(({ label, device, server }) => {
          const snapshot = devices[device];
          return (
            <VD2ServerActions key={device} className="vd2-pdu-card" ariaLabel={label}
              label={label} servers={[{ name: server }]} onRestart={refresh}>
              <h3>{label}</h3>
              <p className="vd2-pdu-device">{device} · {snapshot?.state || 'UNKNOWN'}</p>
              {errors[device] && <p className="vd2-pdu-error" role="alert">{errors[device]}</p>}
              {!snapshot && !errors[device] && <p>Reading outlets…</p>}
              {snapshot?.outputs.map((output) => (
                <label key={output.id} className="vd2-pdu-output">
                  <span>{output.id}. {output.name}</span>
                  <span>{output.state === 1 ? 'ON' : 'OFF'}</span>
                  <input type="checkbox" checked={output.state === 1} disabled={!!busy[device]}
                    aria-label={`${label} output ${output.id} ${output.name}`}
                    onChange={(event) => setOutput(device, output.id, event.target.checked)} />
                </label>
              ))}
            </VD2ServerActions>
          );
        })}
      </div>
    </div>
  );
}
