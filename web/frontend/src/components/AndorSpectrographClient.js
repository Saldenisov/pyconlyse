import React, { useEffect, useState } from 'react';
import { withCsrfToken } from '../api/csrfRequest';

const API_BASE = (process.env.REACT_APP_API_BASE || '/api').replace(/\/$/, '');

const buildPolyline = (yData, width = 900, height = 240) => {
  if (!yData?.length) {
    return '';
  }
  const minY = Math.min(...yData);
  const maxY = Math.max(...yData);
  const spanY = maxY - minY || 1;
  return yData.map((value, index) => {
    const x = (index / Math.max(1, yData.length - 1)) * width;
    const y = height - (((value - minY) / spanY) * height);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');
};

const AndorSpectrographClient = ({ deviceName }) => {
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({
    wavelength_nm: 0,
    grating: 1,
    input_side_slit_um: 0,
    output_side_slit_um: 0,
  });
  const [error, setError] = useState('');

  const refresh = async () => {
    if (!deviceName) {
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/spectrograph/${encodeURIComponent(deviceName)}/info`, {
        credentials: 'include',
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      setInfo(payload.spectrograph_info);
      setForm({
        wavelength_nm: payload.spectrograph_info.wavelength_nm ?? 0,
        grating: payload.spectrograph_info.grating ?? 1,
        input_side_slit_um: payload.spectrograph_info.input_side_slit_um ?? 0,
        output_side_slit_um: payload.spectrograph_info.output_side_slit_um ?? 0,
      });
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 1500);
    return () => window.clearInterval(interval);
  }, [deviceName]);

  const writeParameters = async (updates) => {
    try {
      const url = `${API_BASE}/spectrograph/${encodeURIComponent(deviceName)}/parameters`;
      const response = await fetch(url, withCsrfToken(url, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      }));
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  const runCommand = async (commandName) => {
    try {
      const url = `${API_BASE}/device/${encodeURIComponent(deviceName)}/command/${commandName}`;
      const response = await fetch(url, withCsrfToken(url, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      }));
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="spectroscopy-card">
      <div className="spectroscopy-card-header">
        <h3>{deviceName}</h3>
        <span>{info?.state || 'UNKNOWN'}</span>
      </div>

      {error && <div className="error-alert"><strong>Error:</strong> {error}</div>}

      {info && (
        <>
          <div className="spectroscopy-info-grid">
            <div><strong>Serial:</strong> {info.serial_number}</div>
            <div><strong>Wavelength:</strong> {Number(info.wavelength_nm || 0).toFixed(2)} nm</div>
            <div><strong>Grating:</strong> {info.grating}</div>
            <div><strong>Range:</strong> {info.calibration?.length ? `${info.calibration[0].toFixed(1)} - ${info.calibration[info.calibration.length - 1].toFixed(1)} nm` : 'n/a'}</div>
          </div>

          <div className="spectroscopy-controls">
            <button type="button" onClick={() => runCommand('turn_on')}>On</button>
            <button type="button" onClick={() => runCommand('turn_off')}>Off</button>
            <button type="button" onClick={() => runCommand('RefreshCalibration')}>Refresh calibration</button>
            <button type="button" onClick={() => runCommand('GoToZeroOrder')}>Zero order</button>
          </div>

          <div className="spectroscopy-form-grid">
            <label>
              Center wavelength (nm)
              <input
                type="number"
                step="0.001"
                value={form.wavelength_nm}
                onChange={(event) => setForm((prev) => ({ ...prev, wavelength_nm: event.target.value }))}
                onBlur={() => writeParameters({ wavelength_nm: parseFloat(form.wavelength_nm) })}
              />
            </label>
            <label>
              Grating
              <input
                type="number"
                min="1"
                value={form.grating}
                onChange={(event) => setForm((prev) => ({ ...prev, grating: event.target.value }))}
                onBlur={() => writeParameters({ grating: parseInt(form.grating, 10) })}
              />
            </label>
            <label>
              Input slit (um)
              <input
                type="number"
                min="0"
                value={form.input_side_slit_um}
                onChange={(event) => setForm((prev) => ({ ...prev, input_side_slit_um: event.target.value }))}
                onBlur={() => writeParameters({ input_side_slit_um: parseFloat(form.input_side_slit_um) })}
              />
            </label>
            <label>
              Output slit (um)
              <input
                type="number"
                min="0"
                value={form.output_side_slit_um}
                onChange={(event) => setForm((prev) => ({ ...prev, output_side_slit_um: event.target.value }))}
                onBlur={() => writeParameters({ output_side_slit_um: parseFloat(form.output_side_slit_um) })}
              />
            </label>
          </div>

          <div className="spectroscopy-plot-card">
            <strong>Calibration axis</strong>
            <svg viewBox="0 0 900 240" className="spectroscopy-plot">
              <polyline
                fill="none"
                stroke="#1f77b4"
                strokeWidth="2"
                points={buildPolyline(info.calibration || [])}
              />
            </svg>
          </div>
        </>
      )}
    </div>
  );
};

export default AndorSpectrographClient;
