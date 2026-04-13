import React, { useEffect, useMemo, useState } from 'react';

import AndorNewtonClient from './components/AndorNewtonClient';
import AndorSpectrographClient from './components/AndorSpectrographClient';
import './css/DeviceClients.css';
import './css/SpectroscopyClients.css';

const API_BASE = (process.env.REACT_APP_API_BASE || '/api').replace(/\/$/, '');

const isAndorCamera = (camera) => {
  const fingerprint = `${camera?.name || ''} ${camera?.class || ''} ${camera?.model_name || ''}`.toLowerCase();
  return fingerprint.includes('andor');
};

const SpectroscopyClients = () => {
  const [cameraNames, setCameraNames] = useState([]);
  const [spectrographNames, setSpectrographNames] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const loadDevices = async () => {
      try {
        const [cameraResponse, spectroResponse] = await Promise.all([
          fetch(`${API_BASE}/cameras`, { credentials: 'include' }),
          fetch(`${API_BASE}/spectrographs`, { credentials: 'include' }),
        ]);

        const cameraPayload = await cameraResponse.json();
        const spectroPayload = await spectroResponse.json();

        const andorCameras = (cameraPayload.cameras || [])
          .filter((camera) => isAndorCamera(camera) && camera.available !== false)
          .map((camera) => String(camera.name));
        const andorSpectrographs = (spectroPayload.spectrographs || [])
          .filter((device) => device.available !== false)
          .map((device) => String(device.name));

        if (!cancelled) {
          setCameraNames(andorCameras);
          setSpectrographNames(andorSpectrographs);
          setSelectedCamera((current) => current || andorCameras[0] || '');
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      }
    };

    loadDevices();
    return () => {
      cancelled = true;
    };
  }, []);

  const visibleSpectrographs = useMemo(
    () => [...spectrographNames].sort((left, right) => left.localeCompare(right)),
    [spectrographNames]
  );

  return (
    <div className="device-clients-page spectroscopy-page">
      <div className="page-header">
        <h1>Spectroscopy</h1>
        <p>Unified Andor workspace for Newton CCD together with Shamrock and Kymera spectrographs.</p>
      </div>

      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="spectroscopy-toolbar">
        <label>
          Newton CCD
          <select value={selectedCamera} onChange={(event) => setSelectedCamera(event.target.value)}>
            {cameraNames.map((cameraName) => (
              <option key={cameraName} value={cameraName}>
                {cameraName}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="spectroscopy-layout">
        <div className="spectroscopy-main-panel">
          {selectedCamera ? (
            <AndorNewtonClient cameraName={selectedCamera} panelTitle="Newton CCD" />
          ) : (
            <p>No Andor Newton camera found in `/api/cameras`.</p>
          )}
        </div>

        <div className="spectroscopy-side-panel">
          {visibleSpectrographs.length > 0 ? (
            visibleSpectrographs.map((deviceName) => (
              <AndorSpectrographClient key={deviceName} deviceName={deviceName} />
            ))
          ) : (
            <p>No Andor spectrographs found in `/api/spectrographs`.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default SpectroscopyClients;
