import React, { useEffect, useMemo, useState } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';

const API_BASE = (process.env.REACT_APP_API_BASE || '/api').replace(/\/$/, '');

const buildPolyline = (xData, yData, width = 900, height = 260) => {
  if (!xData?.length || !yData?.length || xData.length !== yData.length) {
    return '';
  }

  const minX = Math.min(...xData);
  const maxX = Math.max(...xData);
  const minY = Math.min(...yData);
  const maxY = Math.max(...yData);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;

  return yData.map((value, index) => {
    const x = ((xData[index] - minX) / spanX) * width;
    const y = height - (((value - minY) / spanY) * height);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');
};

const trackColors = ['#1f77b4', '#d62728', '#2ca02c', '#9467bd'];

const AndorNewtonClient = ({ cameraName, panelTitle = 'Andor Newton CCD' }) => {
  const [cameraInfo, setCameraInfo] = useState(null);
  const [imageData, setImageData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    exposure_time: 0.001,
    gain: 0,
    number_kinetics: 1,
    trigger_mode: 1,
  });

  useEffect(() => {
    if (!cameraName) {
      return undefined;
    }

    let cancelled = false;

    const refresh = async () => {
      try {
        const [infoResponse, imageResponse] = await Promise.all([
          fetch(`${API_BASE}/camera/${encodeURIComponent(cameraName)}/info`, { credentials: 'include' }),
          fetch(`${API_BASE}/camera/${encodeURIComponent(cameraName)}/image`, { credentials: 'include' }),
        ]);

        const infoPayload = await infoResponse.json();
        if (!cancelled && infoPayload.success) {
          setCameraInfo(infoPayload.camera_info);
          setForm({
            exposure_time: infoPayload.camera_info.exposure_time ?? 0.001,
            gain: infoPayload.camera_info.gain ?? 0,
            number_kinetics: infoPayload.camera_info.number_kinetics ?? 1,
            trigger_mode: infoPayload.camera_info.trigger_mode ?? 1,
          });
        }

        const imagePayload = await imageResponse.json();
        if (!cancelled && imagePayload.success) {
          setImageData(Array.isArray(imagePayload.image) ? imagePayload.image : []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      }
    };

    refresh();
    const interval = window.setInterval(refresh, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [cameraName]);

  const runGrabbingAction = async (action) => {
    if (!cameraName) {
      return;
    }
    setLoading(true);
    setError('');
    try {
      const url = `${API_BASE}/camera/${encodeURIComponent(cameraName)}/grabbing`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const writeParameters = async (updates) => {
    if (!cameraName) {
      return;
    }
    setLoading(true);
    setError('');
    try {
      const url = `${API_BASE}/camera/${encodeURIComponent(cameraName)}/parameters`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const spectralPayload = useMemo(() => {
    if (!cameraInfo || !Array.isArray(imageData) || imageData.length === 0) {
      return { wavelengths: [], tracks: [] };
    }

    const wavelengths = Array.isArray(cameraInfo.wavelengths_axis) && cameraInfo.wavelengths_axis.length > 0
      ? cameraInfo.wavelengths_axis
      : imageData[0]?.map((_, index) => index) || [];

    const tracks = imageData.map((track) => Array.isArray(track) ? track : []);
    return { wavelengths, tracks };
  }, [cameraInfo, imageData]);

  return (
    <div className="spectroscopy-card">
      <div className="spectroscopy-card-header">
        <h2>{panelTitle}</h2>
        <span>{cameraName || 'No camera selected'}</span>
      </div>

      {error && <div className="error-alert"><strong>Error:</strong> {error}</div>}

      {cameraInfo && (
        <>
          <div className="spectroscopy-info-grid">
            <div><strong>Model:</strong> {cameraInfo.camera_model_name}</div>
            <div><strong>Serial:</strong> {cameraInfo.camera_serial_number}</div>
            <div><strong>State:</strong> {cameraInfo.state}</div>
            <div><strong>Tracks:</strong> {cameraInfo.track_count}</div>
            <div><strong>Pixels:</strong> {cameraInfo.width}</div>
            <div><strong>Cooling:</strong> {String(cameraInfo.cooler_on)}</div>
          </div>

          <div className="spectroscopy-controls">
            <button type="button" disabled={loading} onClick={() => runGrabbingAction('start')}>
              Start
            </button>
            <button type="button" disabled={loading} onClick={() => runGrabbingAction('stop')}>
              Stop
            </button>
          </div>

          <div className="spectroscopy-form-grid">
            <label>
              Exposure (s)
              <input
                type="number"
                step="0.000001"
                value={form.exposure_time}
                onChange={(event) => setForm((prev) => ({ ...prev, exposure_time: event.target.value }))}
                onBlur={() => writeParameters({ exposure_time: parseFloat(form.exposure_time) })}
              />
            </label>
            <label>
              Gain
              <input
                type="number"
                value={form.gain}
                onChange={(event) => setForm((prev) => ({ ...prev, gain: event.target.value }))}
                onBlur={() => writeParameters({ gain: parseInt(form.gain, 10) })}
              />
            </label>
            <label>
              Kinetics
              <input
                type="number"
                min="1"
                value={form.number_kinetics}
                onChange={(event) => setForm((prev) => ({ ...prev, number_kinetics: event.target.value }))}
                onBlur={() => writeParameters({ number_kinetics: parseInt(form.number_kinetics, 10) })}
              />
            </label>
            <label>
              Trigger
              <select
                value={form.trigger_mode}
                onChange={(event) => {
                  const nextValue = parseInt(event.target.value, 10);
                  setForm((prev) => ({ ...prev, trigger_mode: nextValue }));
                  writeParameters({ trigger_mode: nextValue });
                }}
              >
                <option value={0}>Internal</option>
                <option value={1}>External</option>
                <option value={10}>Software</option>
              </select>
            </label>
          </div>

          <div className="spectroscopy-plot-card">
            <div className="spectroscopy-plot-header">
              <strong>Live spectral tracks</strong>
              <span>
                Linked spectrograph: {cameraInfo.linked_spectrograph_device || 'none'}
              </span>
            </div>
            <svg viewBox="0 0 900 260" className="spectroscopy-plot">
              {spectralPayload.tracks.map((track, index) => (
                <polyline
                  key={`track-${index}`}
                  fill="none"
                  stroke={trackColors[index % trackColors.length]}
                  strokeWidth="2"
                  points={buildPolyline(spectralPayload.wavelengths, track)}
                />
              ))}
            </svg>
          </div>
        </>
      )}
    </div>
  );
};

export default AndorNewtonClient;
