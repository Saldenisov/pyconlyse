import React, { useState, useEffect, useRef } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import './CameraClient.css';

const CameraClient = ({
  initialCamera = null,
  lockCameraName = null,
  hideSelector = false,
  panelTitle = 'Camera Control',
}) => {
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [cameraInfo, setCameraInfo] = useState(null);
  const [parameters, setParameters] = useState({});
  const [isGrabbing, setIsGrabbing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [imageData, setImageData] = useState(null);
  const [cgPosition, setCgPosition] = useState(null);
  const canvasRef = useRef(null);

  const API_BASE = (process.env.REACT_APP_API_BASE || '/api').replace(/\/$/, '');
  const toBoolean = (value) => {
    if (typeof value === 'boolean') {
      return value;
    }
    if (typeof value === 'number') {
      return value !== 0;
    }
    if (typeof value === 'string') {
      const normalized = value.trim().toLowerCase();
      if (['1', 'true', 'yes', 'on', 'running'].includes(normalized)) {
        return true;
      }
      if (['0', 'false', 'no', 'off', 'stopped'].includes(normalized)) {
        return false;
      }
    }
    return Boolean(value);
  };

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // Load cameras on mount
  useEffect(() => {
    loadCameras();
  }, []);

  useEffect(() => {
    setImageData(null);
    setCgPosition(null);
  }, [selectedCamera]);

  // Poll camera status when selected
  useEffect(() => {
    if (selectedCamera) {
      loadCameraInfo();
      const interval = setInterval(() => {
        loadCameraInfo();
        if (isGrabbing) {
          loadImage();
        }
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [selectedCamera, isGrabbing]);

  const loadCameras = async () => {
    try {
      const response = await fetch(`${API_BASE}/cameras`);
      const data = await response.json();
      if (data.success) {
        setCameras(data.cameras);

        if (lockCameraName) {
          const lockedCamera = data.cameras.find((cam) => cam.name === lockCameraName);
          if (lockedCamera) {
            setSelectedCamera(lockCameraName);
            setError(null);
          } else {
            setSelectedCamera(null);
            setError(`Locked camera ${lockCameraName} is not available`);
          }
          return;
        }

        if (data.cameras.length > 0 && !selectedCamera) {
          const preferredCamera = initialCamera
            ? data.cameras.find((cam) => cam.name === initialCamera)
            : null;
          setSelectedCamera(preferredCamera ? preferredCamera.name : data.cameras[0].name);
        }
      }
    } catch (err) {
      setError('Failed to load cameras: ' + err.message);
    }
  };

  const loadCameraInfo = async () => {
    if (!selectedCamera) return;
    
    try {
      const response = await fetch(`${API_BASE}/camera/${encodeURIComponent(selectedCamera)}/info`);
      const data = await response.json();
      if (data.success) {
        setCameraInfo(data.camera_info);
        setParameters({
          exposure_time: data.camera_info.exposure_time,
          gain: data.camera_info.gain,
          width: data.camera_info.width,
          height: data.camera_info.height,
          offsetX: data.camera_info.offsetX,
          offsetY: data.camera_info.offsetY,
        });
        setIsGrabbing(toBoolean(data.camera_info.isgrabbing));
      }
    } catch (err) {
      console.error('Failed to load camera info:', err);
    }
  };

  const pollGrabbingState = async (expectedState, attempts = 6, delayMs = 250) => {
    let latestState = null;

    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        const response = await fetch(`${API_BASE}/camera/${encodeURIComponent(selectedCamera)}/grabbing`);
        const data = await response.json();
        if (data.success) {
          latestState = toBoolean(data.grabbing);
          if (latestState === expectedState) {
            return latestState;
          }
        }
      } catch (err) {
        // Ignore transient errors while polling, we keep latest known state.
      }

      await sleep(delayMs);
    }

    if (latestState === null) {
      return expectedState;
    }
    return latestState;
  };

  const loadImage = async () => {
    if (!selectedCamera) return;
    
    try {
      const response = await fetch(`${API_BASE}/camera/${encodeURIComponent(selectedCamera)}/image`);
      const data = await response.json();
      if (data.success && data.image) {
        setImageData(data.image);
        setCgPosition(data.cg_position);
        drawImage(data.image, data.cg_position);
      }
    } catch (err) {
      console.error('Failed to load image:', err);
    }
  };

  const drawImage = (imageArray, cg) => {
    const canvas = canvasRef.current;
    if (!canvas || !imageArray) return;

    const ctx = canvas.getContext('2d');
    
    // Image is stored as 2D array [channels*height, width] for RGB
    // Need to reconstruct to proper dimensions
    const height = Math.floor(imageArray.length / 3);
    const width = imageArray[0].length;
    
    canvas.width = width;
    canvas.height = height;
    
    // Create ImageData
    const imgData = ctx.createImageData(width, height);
    
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        imgData.data[idx] = imageArray[y][x];           // R
        imgData.data[idx + 1] = imageArray[y + height][x]; // G
        imgData.data[idx + 2] = imageArray[y + height * 2][x]; // B
        imgData.data[idx + 3] = 255;                    // A
      }
    }
    
    ctx.putImageData(imgData, 0, 0);
    
    // Draw center of gravity marker
    if (cg && cg.X && cg.Y) {
      ctx.strokeStyle = 'red';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cg.X, cg.Y, 10, 0, 2 * Math.PI);
      ctx.stroke();
      
      // Draw crosshair
      ctx.beginPath();
      ctx.moveTo(cg.X - 15, cg.Y);
      ctx.lineTo(cg.X + 15, cg.Y);
      ctx.moveTo(cg.X, cg.Y - 15);
      ctx.lineTo(cg.X, cg.Y + 15);
      ctx.stroke();
    }
  };

  const handleStartGrabbing = async () => {
    setLoading(true);
    try {
      const url = `${API_BASE}/camera/${encodeURIComponent(selectedCamera)}/grabbing`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'start' })
      });
      const data = await response.json();
      if (data.success) {
        const confirmedState = await pollGrabbingState(true);
        setIsGrabbing(confirmedState);
        if (!confirmedState) {
          setError('Start command sent, but camera still reports grabbing OFF.');
        } else {
          setError(null);
          loadImage();
        }
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to start grabbing: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStopGrabbing = async () => {
    setLoading(true);
    try {
      const url = `${API_BASE}/camera/${encodeURIComponent(selectedCamera)}/grabbing`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'stop' })
      });
      const data = await response.json();
      if (data.success) {
        const confirmedState = await pollGrabbingState(false);
        setIsGrabbing(confirmedState);
        if (!confirmedState) {
          setImageData(null);
          setCgPosition(null);
          const canvas = canvasRef.current;
          if (canvas) {
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
          }
          setError(null);
        } else {
          setError('Stop command sent, but camera still reports grabbing ON.');
        }
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to stop grabbing: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleParameterChange = async (paramName, value) => {
    setLoading(true);
    try {
      const url = `${API_BASE}/camera/${encodeURIComponent(selectedCamera)}/parameters`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [paramName]: parseFloat(value) })
      });
      const data = await response.json();
      if (data.success) {
        setParameters(prev => ({ ...prev, [paramName]: value }));
        loadCameraInfo();
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to set parameter: ' + err.message);
    }
    setLoading(false);
  };

  const handleTrigger = async () => {
    setLoading(true);
    try {
      const url = `${API_BASE}/camera/${encodeURIComponent(selectedCamera)}/trigger`;
      const response = await fetchWithHardwareApproval(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await response.json();
      if (!data.success) {
        setError(data.error);
      }
    } catch (err) {
      setError('Failed to trigger: ' + err.message);
    }
    setLoading(false);
  };

  return (
    <div className="camera-client">
      <div className="camera-header">
        <h2>{panelTitle}</h2>
        {hideSelector ? (
          <div className="camera-select" style={{ pointerEvents: 'none', opacity: 0.9 }}>
            {selectedCamera || lockCameraName || 'No camera selected'}
          </div>
        ) : (
          <select
            value={selectedCamera || ''}
            onChange={(e) => setSelectedCamera(e.target.value)}
            className="camera-select"
            disabled={Boolean(lockCameraName)}
          >
            {cameras.map(cam => (
              <option key={cam.name} value={cam.name}>
                {cam.friendly_name || cam.name} ({cam.state})
              </option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <div className="error-message">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {cameraInfo && (
        <div className="camera-content">
          <div className="camera-info-panel">
            <h3>Camera Information</h3>
            <div className="info-grid">
              <div className="info-item">
                <span className="info-label">Model:</span>
                <span className="info-value">{cameraInfo.camera_model_name}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Serial:</span>
                <span className="info-value">{cameraInfo.camera_serial_number}</span>
              </div>
              <div className="info-item">
                <span className="info-label">State:</span>
                <span className={`info-value state-${cameraInfo.state.toLowerCase()}`}>
                  {cameraInfo.state}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Frame Rate:</span>
                <span className="info-value">{cameraInfo.framerate?.toFixed(2)} fps</span>
              </div>
            </div>

            <h3>Camera Controls</h3>
            <div className="controls-panel">
              <div className="control-buttons">
                {!isGrabbing ? (
                  <button 
                    onClick={handleStartGrabbing} 
                    disabled={loading}
                    className="btn-start"
                  >
                    Start Grabbing
                  </button>
                ) : (
                  <button 
                    onClick={handleStopGrabbing} 
                    disabled={loading}
                    className="btn-stop"
                  >
                    Stop Grabbing
                  </button>
                )}
                <button 
                  onClick={handleTrigger} 
                  disabled={loading || !isGrabbing}
                  className="btn-trigger"
                >
                  Software Trigger
                </button>
              </div>

              <div className="parameters">
                <div className="param-group">
                  <label>Exposure Time (µs)</label>
                  <input 
                    type="number"
                    value={parameters.exposure_time || 0}
                    onChange={(e) => setParameters(prev => ({ ...prev, exposure_time: e.target.value }))}
                    onBlur={(e) => handleParameterChange('exposure_time', e.target.value)}
                    min={cameraInfo.exposure_min}
                    max={cameraInfo.exposure_max}
                  />
                  <span className="param-range">
                    ({cameraInfo.exposure_min} - {cameraInfo.exposure_max})
                  </span>
                </div>

                <div className="param-group">
                  <label>Gain</label>
                  <input 
                    type="number"
                    value={parameters.gain || 0}
                    onChange={(e) => setParameters(prev => ({ ...prev, gain: e.target.value }))}
                    onBlur={(e) => handleParameterChange('gain', e.target.value)}
                    min={cameraInfo.gain_min}
                    max={cameraInfo.gain_max}
                  />
                  <span className="param-range">
                    ({cameraInfo.gain_min} - {cameraInfo.gain_max})
                  </span>
                </div>

                <div className="param-group">
                  <label>Width</label>
                  <input 
                    type="number"
                    value={parameters.width || 0}
                    onChange={(e) => setParameters(prev => ({ ...prev, width: e.target.value }))}
                    onBlur={(e) => handleParameterChange('width', e.target.value)}
                    min={cameraInfo.width_min}
                    max={cameraInfo.width_max}
                  />
                </div>

                <div className="param-group">
                  <label>Height</label>
                  <input 
                    type="number"
                    value={parameters.height || 0}
                    onChange={(e) => setParameters(prev => ({ ...prev, height: e.target.value }))}
                    onBlur={(e) => handleParameterChange('height', e.target.value)}
                    min={cameraInfo.height_min}
                    max={cameraInfo.height_max}
                  />
                </div>
              </div>
            </div>

            {cgPosition && (
              <div className="cg-info">
                <h4>Center of Gravity</h4>
                <p>X: {cgPosition.X}, Y: {cgPosition.Y}</p>
              </div>
            )}
          </div>

          <div className="camera-preview-panel">
            <h3>Live Preview</h3>
            <div className="preview-container">
              <canvas ref={canvasRef} className="camera-canvas" />
              {!imageData && (
                <div className="no-image">
                  {isGrabbing ? 'Waiting for image...' : 'Start grabbing to see preview'}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CameraClient;
