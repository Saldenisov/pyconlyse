import React, { useEffect, useMemo, useState } from 'react';
import CameraClient from './components/CameraClient';
import { withCsrfToken } from './api/csrfRequest';
import './css/DeviceClients.css';
import './css/CamerasClients.css';

const API_BASE = (process.env.REACT_APP_API_BASE || '/api').replace(/\/$/, '');

const isBaslerCamera = (camera) => {
  const fingerprint = `${camera?.name || ''} ${camera?.class || ''} ${camera?.model_name || ''}`.toLowerCase();
  return fingerprint.includes('basler');
};

const CamerasClients = () => {
  const [availableCameras, setAvailableCameras] = useState([]);
  const [offlineCameras, setOfflineCameras] = useState([]);
  const [selectedCameraNames, setSelectedCameraNames] = useState([]);
  const [loadedCameraNames, setLoadedCameraNames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [error, setError] = useState('');
  const [bulkSummary, setBulkSummary] = useState('');

  const selectedCount = selectedCameraNames.length;

  const sortedAvailableCameras = useMemo(
    () => [...availableCameras].sort((a, b) => a.localeCompare(b)),
    [availableCameras]
  );

  useEffect(() => {
    let cancelled = false;

    const loadCameras = async () => {
      setLoading(true);
      setError('');
      setBulkSummary('');

      try {
        const response = await fetch(`${API_BASE}/cameras`, { credentials: 'include' });
        if (!response.ok) {
          throw new Error(`Camera list failed (${response.status})`);
        }

        const payload = await response.json();
        const baslerCameras = (payload.cameras || []).filter(isBaslerCamera);
        const onlineNames = baslerCameras
          .filter((camera) => camera?.available !== false)
          .map((camera) => String(camera.name));
        const offline = baslerCameras
          .filter((camera) => camera?.available === false)
          .map((camera) => ({
            name: String(camera.name),
            state: String(camera.state || 'UNKNOWN'),
            error: String(camera.error || 'Not reachable'),
          }));

        if (!cancelled) {
          setAvailableCameras(onlineNames);
          setOfflineCameras(offline);
          setSelectedCameraNames([]);
          setLoadedCameraNames([]);
        }
      } catch (err) {
        if (!cancelled) {
          setAvailableCameras([]);
          setOfflineCameras([]);
          setSelectedCameraNames([]);
          setLoadedCameraNames([]);
          setError(err.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadCameras();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshList = async () => {
    setLoading(true);
    setError('');
    setBulkSummary('');

    try {
      const response = await fetch(`${API_BASE}/cameras`, { credentials: 'include' });
      if (!response.ok) {
        throw new Error(`Camera list failed (${response.status})`);
      }
      const payload = await response.json();
      const baslerCameras = (payload.cameras || []).filter(isBaslerCamera);
      const onlineNames = baslerCameras
        .filter((camera) => camera?.available !== false)
        .map((camera) => String(camera.name));
      const offline = baslerCameras
        .filter((camera) => camera?.available === false)
        .map((camera) => ({
          name: String(camera.name),
          state: String(camera.state || 'UNKNOWN'),
          error: String(camera.error || 'Not reachable'),
        }));

      setAvailableCameras(onlineNames);
      setOfflineCameras(offline);
      setSelectedCameraNames((current) => current.filter((name) => onlineNames.includes(name)));
      setLoadedCameraNames((current) => current.filter((name) => onlineNames.includes(name)));
    } catch (err) {
      setError(err.message);
      setAvailableCameras([]);
      setOfflineCameras([]);
      setSelectedCameraNames([]);
      setLoadedCameraNames([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleCamera = (cameraName) => {
    setSelectedCameraNames((current) => {
      if (current.includes(cameraName)) {
        return current.filter((name) => name !== cameraName);
      }
      return [...current, cameraName].sort((a, b) => a.localeCompare(b));
    });
  };

  const selectAll = () => {
    setSelectedCameraNames(sortedAvailableCameras);
  };

  const clearSelection = () => {
    setSelectedCameraNames([]);
  };

  const loadSelected = () => {
    setLoadedCameraNames([...selectedCameraNames].sort((a, b) => a.localeCompare(b)));
  };

  const runBulkGrabbingAction = async (action) => {
    if (loadedCameraNames.length === 0) {
      return;
    }

    setBulkLoading(true);
    setError('');
    setBulkSummary('');

    const results = await Promise.all(
      loadedCameraNames.map(async (cameraName) => {
        try {
          const url = `${API_BASE}/camera/${encodeURIComponent(cameraName)}/grabbing`;
          const response = await fetch(url, withCsrfToken(url, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
          }));
          const payload = await response.json();
          if (!response.ok || !payload.success) {
            throw new Error(payload.error || `HTTP ${response.status}`);
          }
          return { cameraName, success: true };
        } catch (err) {
          return { cameraName, success: false, error: err.message };
        }
      })
    );

    const failed = results.filter((result) => !result.success);
    if (failed.length > 0) {
      const details = failed.map((result) => `${result.cameraName}: ${result.error}`).join('; ');
      setError(`Bulk ${action} finished with errors. ${details}`);
      setBulkSummary(
        `${results.length - failed.length} / ${results.length} cameras ${action === 'start' ? 'started' : 'stopped'}.`
      );
    } else {
      setBulkSummary(`All ${results.length} loaded cameras ${action === 'start' ? 'started' : 'stopped'}.`);
    }

    setBulkLoading(false);
  };

  return (
    <div className="device-clients-page camera-clients-page">
      <div className="page-header">
        <h1>Basler Cameras</h1>
        <p>Select one camera or all three, then load panels to monitor and control each camera.</p>
      </div>

      {loading && <p>Loading camera devices...</p>}
      {error && (
        <div className="error-alert">
          <strong>Error:</strong> {error}
        </div>
      )}
      {bulkSummary && !error && <div className="bulk-summary">{bulkSummary}</div>}

      {!loading && !error && sortedAvailableCameras.length === 0 && (
        <div style={{ marginTop: '12px' }}>
          <p>No `DS_Basler_camera` devices found in `/api/cameras`.</p>
          {offlineCameras.length > 0 && (
            <>
              <p>Offline cameras:</p>
              <ul className="offline-list">
                {offlineCameras.map((camera) => (
                  <li key={camera.name}>
                    {camera.name} ({camera.state})
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {!loading && !error && sortedAvailableCameras.length > 0 && (
        <>
          <div className="camera-selection-panel">
            <h3>Choose Cameras</h3>
            <div className="camera-selection-actions">
              <button type="button" onClick={refreshList}>
                Refresh
              </button>
              <button type="button" onClick={selectAll}>
                Select All
              </button>
              <button type="button" onClick={clearSelection}>
                Clear
              </button>
              <button type="button" onClick={loadSelected} disabled={selectedCount === 0}>
                Load Selected ({selectedCount})
              </button>
            </div>
            <div className="camera-list">
              {sortedAvailableCameras.map((cameraName) => (
                <label key={cameraName} className="camera-row">
                  <input
                    type="checkbox"
                    checked={selectedCameraNames.includes(cameraName)}
                    onChange={() => toggleCamera(cameraName)}
                  />
                  <span>{cameraName}</span>
                </label>
              ))}
            </div>
          </div>

          {offlineCameras.length > 0 && (
            <div className="offline-panel">
              <h4>Offline Cameras</h4>
              <ul className="offline-list">
                {offlineCameras.map((camera) => (
                  <li key={camera.name} title={camera.error}>
                    {camera.name} ({camera.state})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {loadedCameraNames.length > 0 ? (
            <>
              <div className="camera-bulk-controls">
                <button
                  type="button"
                  className="bulk-start"
                  disabled={bulkLoading}
                  onClick={() => runBulkGrabbingAction('start')}
                >
                  Start All Loaded
                </button>
                <button
                  type="button"
                  className="bulk-stop"
                  disabled={bulkLoading}
                  onClick={() => runBulkGrabbingAction('stop')}
                >
                  Stop All Loaded
                </button>
                <span>{loadedCameraNames.length} camera panels loaded</span>
              </div>

              <div className="camera-panels-grid">
                {loadedCameraNames.map((cameraName) => (
                  <div className="camera-panel-card" key={cameraName}>
                    <CameraClient
                      lockCameraName={cameraName}
                      hideSelector
                      panelTitle={cameraName}
                    />
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p>Select one or multiple cameras and click `Load Selected`.</p>
          )}
        </>
      )}
    </div>
  );
};

export default CamerasClients;
