import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import useFrameDisplayRate from '../useFrameDisplayRate';
import FrameDisplayRate from './FrameDisplayRate';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import { API_BASE } from "./LaserPointingController.API_BASE";
import { actuatorVisualState } from "./LaserPointingController.API_BASE";
import { finiteNumber } from "./LaserPointingController.API_BASE";
import { roundnessError } from "./LaserPointingController.API_BASE";
import { centeringError } from "./LaserPointingController.API_BASE";
import { CAMERA_NUMERIC_PARAMETERS } from "./LaserPointingController.API_BASE";
import { CAMERA_PARAMETER_NAMES } from "./LaserPointingController.API_BASE";
import { CAMERA_ADVANCED_PARAMETERS } from "./LaserPointingController.API_BASE";
import { PROFILE_COLORS } from "./LaserPointingController.API_BASE";
import { alignmentActivityText } from "./LaserPointingController.API_BASE";
import { BeamProfileSummary } from "./LaserPointingController.API_BASE";
import { measuredProfileSnapshot } from "./LaserPointingController.API_BASE";
import { drawBeamOverlays } from "./LaserPointingController.API_BASE";

export const CameraPreview = ({
  camera,
  controllerName = '',
  enabled = true,
  state = 'UNKNOWN',
  history = [],
  progress = {},
  tolerance = 0,
  hasTranslation = false,
  showAutomaticContours = false,
  onRefresh,
}) => {
  const canvasRef = useRef(null);
  const frameRequestInFlight = useRef(false);
  const [frame, setFrame] = useState(null);
  const [centroid, setCentroid] = useState(null);
  const [liveContours, setLiveContours] = useState([]);
  const [frameError, setFrameError] = useState('');
  const [controlError, setControlError] = useState('');
  const [cameraAction, setCameraAction] = useState('');
  const [cameraInfo, setCameraInfo] = useState({});
  const [parameters, setParameters] = useState({});
  const [parameterBusy, setParameterBusy] = useState('');
  const [cameraControlsLoaded, setCameraControlsLoaded] = useState(false);
  const [cameraInfoLoading, setCameraInfoLoading] = useState(false);
  const [requestedGrabbing, setRequestedGrabbing] = useState(null);
  const previewEnabled = requestedGrabbing ?? enabled;
  const activity = alignmentActivityText(progress);
  const beamContours = useMemo(
    () => (Array.isArray(progress?.beam_shape?.contours)
      ? progress.beam_shape.contours : []),
    [progress]
  );
  const profileSnapshot = useMemo(
    () => measuredProfileSnapshot(progress),
    [progress]
  );
  const displayedContours = showAutomaticContours ? liveContours : beamContours;
  const useMeasuredSnapshot = !showAutomaticContours && profileSnapshot && beamContours.length > 0;
  const { hz, frameDisplayed } = useFrameDisplayRate(camera,
    Boolean(previewEnabled && !useMeasuredSnapshot));

  useEffect(() => {
    if (requestedGrabbing !== null
      && enabled === requestedGrabbing
      && !cameraAction) {
      setRequestedGrabbing(null);
    }
  }, [cameraAction, enabled, requestedGrabbing]);

  const loadCameraInfo = useCallback(async () => {
    if (!camera) return;
    try {
      const response = await fetch(
        `${API_BASE}/camera/${encodeURIComponent(camera)}/info`,
        { credentials: 'include' }
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `Camera information failed (${response.status})`);
      }
      const nextInfo = payload.camera_info || {};
      const nextParameters = {};
      CAMERA_PARAMETER_NAMES.forEach((name) => {
        if (nextInfo[name] !== undefined && nextInfo[name] !== null) {
          nextParameters[name] = nextInfo[name];
        }
      });
      setCameraInfo(nextInfo);
      setParameters(nextParameters);
    } catch (requestError) {
      setControlError(requestError.message);
    }
  }, [camera]);

  useEffect(() => {
    setCameraInfo({});
    setParameters({});
    setCameraControlsLoaded(false);
    setCameraInfoLoading(false);
  }, [camera]);

  useEffect(() => {
    if (camera) loadCameraInfo();
  }, [camera, loadCameraInfo]);

  const handleCameraControlsToggle = async (event) => {
    if (!event.currentTarget.open || cameraControlsLoaded) return;
    setCameraControlsLoaded(true);
    setCameraInfoLoading(true);
    await loadCameraInfo();
    setCameraInfoLoading(false);
  };

  const loadFrame = useCallback(async () => {
    if (!camera || frameRequestInFlight.current) return;
    frameRequestInFlight.current = true;
    try {
      const response = await fetch(
        `${API_BASE}/camera/${encodeURIComponent(camera)}/image${showAutomaticContours ? '?contours=1' : ''}`,
        { credentials: 'include' }
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        if (response.status === 409 && payload.grabbing === false) {
          setFrame(null);
          setCentroid(null);
          setLiveContours([]);
          setFrameError('');
          return;
        }
        throw new Error(payload.error || `Image request failed (${response.status})`);
      }
      setFrame(payload.image);
      setCentroid(payload.cg_position || null);
      setLiveContours(Array.isArray(payload.contours) ? payload.contours : []);
      setFrameError('');
    } catch (requestError) {
      setFrameError(requestError.message);
    } finally {
      frameRequestInFlight.current = false;
    }
  }, [camera, showAutomaticContours]);

  useEffect(() => {
    if (!previewEnabled) {
      setFrame(null);
      setCentroid(null);
      setLiveContours([]);
      setFrameError('');
      return undefined;
    }
    loadFrame();
    const timer = setInterval(loadFrame, 1000);
    return () => clearInterval(timer);
  }, [previewEnabled, loadFrame]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    if (useMeasuredSnapshot) {
      let active = true;
      const measuredImage = new Image();
      measuredImage.onload = () => {
        if (!active) return;
        canvas.width = measuredImage.naturalWidth;
        canvas.height = measuredImage.naturalHeight;
        const context = canvas.getContext('2d');
        context.drawImage(measuredImage, 0, 0);
        drawBeamOverlays(
          context,
          measuredImage.naturalWidth,
          profileSnapshot.centroid,
          beamContours
        );
      };
      measuredImage.src = profileSnapshot.dataUrl;
      return () => {
        active = false;
      };
    }

    if (!Array.isArray(frame) || !frame.length || !Array.isArray(frame[0])) return undefined;
    const height = Math.floor(frame.length / 3);
    const width = frame[0].length;
    if (!height || !width) return undefined;

    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d');
    const image = context.createImageData(width, height);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const offset = (y * width + x) * 4;
        image.data[offset] = frame[y][x];
        image.data[offset + 1] = frame[y + height][x];
        image.data[offset + 2] = frame[y + 2 * height][x];
        image.data[offset + 3] = 255;
      }
    }
    context.putImageData(image, 0, 0);
    drawBeamOverlays(context, width, centroid, displayedContours);
    frameDisplayed(frame, camera);
    return undefined;
  }, [frame, centroid, beamContours, displayedContours, profileSnapshot, useMeasuredSnapshot, frameDisplayed, camera]);

  const setCameraGrabbing = async (action) => {
    if (!camera || cameraAction) return;
    const expectedGrabbing = action === 'start';
    if (!expectedGrabbing) {
      // Stop preview reads before sending StopGrabbing.  Reading the Tango
      // image attribute while stopped is active behavior: it starts grabbing.
      setRequestedGrabbing(false);
    }
    setCameraAction(action);
    setControlError('');
    try {
      const response = await fetchWithHardwareApproval(
        `${API_BASE}/camera/${encodeURIComponent(camera)}/grabbing`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ action }),
        }
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `Camera ${action} failed (${response.status})`);
      }
      if (Boolean(payload.grabbing) !== expectedGrabbing || payload.state_confirmed === false) {
        throw new Error(
          `${action === 'start' ? 'Start' : 'Stop'} command sent, but the camera still reports grabbing ${payload.grabbing ? 'ON' : 'OFF'}.`
        );
      }
      setRequestedGrabbing(expectedGrabbing);
      if (onRefresh) await onRefresh();
      await loadCameraInfo();
    } catch (requestError) {
      setRequestedGrabbing(null);
      setControlError(requestError.message);
    } finally {
      setCameraAction('');
    }
  };

  const writeParameter = async (name, nextValue) => {
    const rawValue = nextValue ?? parameters[name];
    if (!camera || parameterBusy || rawValue === undefined || rawValue === '') return;
    const value = name === 'format_pixel' ? rawValue : Number(rawValue);
    if (name !== 'format_pixel' && !Number.isFinite(value)) {
      setControlError(`${name} must be a number.`);
      return;
    }
    const definition = CAMERA_NUMERIC_PARAMETERS.find((item) => item.name === name);
    const minimum = finiteNumber(definition?.minValue ?? cameraInfo[definition?.min]);
    const maximum = finiteNumber(definition?.maxValue ?? cameraInfo[definition?.max]);
    if (name !== 'format_pixel' && minimum !== null && value < minimum) {
      setControlError(`${definition?.label || name} must be at least ${minimum}.`);
      return;
    }
    if (name !== 'format_pixel' && maximum !== null && value > maximum) {
      setControlError(`${definition?.label || name} must be at most ${maximum}.`);
      return;
    }
    if (String(value) === String(cameraInfo[name])) return;

    setParameterBusy(name);
    setControlError('');
    try {
      const response = await fetchWithHardwareApproval(
        `${API_BASE}/camera/${encodeURIComponent(camera)}/parameters`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ [name]: value }),
        }
      );
      const payload = await response.json();
      const result = payload.results?.[name];
      if (!response.ok || !payload.success || result?.success === false) {
        throw new Error(result?.error || payload.error || `${name} update failed (${response.status})`);
      }
      const confirmedValue = result?.value ?? value;
      setCameraInfo((current) => ({ ...current, [name]: confirmedValue }));
      setParameters((current) => ({ ...current, [name]: confirmedValue }));
      if (onRefresh) await onRefresh();
    } catch (requestError) {
      setControlError(requestError.message);
    } finally {
      setParameterBusy('');
    }
  };

  return (
    <section className="laser-camera-panel">
      <div className="laser-section-heading">
        <strong>Basler preview</strong>
        <span>{camera || 'Camera unavailable'}</span>
      </div>
      {camera && (
        <div className="laser-camera-toolbar">
          <span>{previewEnabled ? 'Grabbing' : `Acquisition stopped · device ${state}`}</span>
          <div className="laser-camera-actions">
            <label className="laser-threshold-control">
              <span>Threshold CG</span>
              <input
                aria-label={`${controllerName || camera} threshold CG`}
                type="number"
                value={parameters.center_gravity_threshold ?? ''}
                min={0}
                max={255}
                step={1}
                disabled={Boolean(parameterBusy) || cameraInfoLoading}
                onChange={(event) => setParameters((current) => ({
                  ...current,
                  center_gravity_threshold: event.target.value,
                }))}
                onBlur={() => writeParameter('center_gravity_threshold')}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') event.currentTarget.blur();
                }}
              />
            </label>
            <button
              type="button"
              onClick={() => setCameraGrabbing(previewEnabled ? 'stop' : 'start')}
              disabled={Boolean(cameraAction)}
            >
              {['start', 'stop'].includes(cameraAction)
                ? `${cameraAction === 'start' ? 'Starting' : 'Stopping'} camera…`
                : `${previewEnabled ? 'Stop' : 'Start'} camera`}
            </button>
          </div>
        </div>
      )}
      <div className="laser-camera-frame">
        <canvas ref={canvasRef} />
        <FrameDisplayRate hz={hz} />
        {showAutomaticContours && displayedContours.length > 0 && (
          <div className="laser-profile-frame-label">
            Live scoring contours
          </div>
        )}
        {useMeasuredSnapshot && (
          <div className="laser-profile-frame-label">
            {`Measured profile frame${profileSnapshot.point ? ` · ${String(profileSnapshot.point).replace(/point/i, 'point ')}` : ''}`}
          </div>
        )}
        {activity && (
          <div className={`laser-camera-activity phase-${String(progress.phase || '').replace(/_/g, '-')}`}>
            <strong>{activity.title}</strong>
            {activity.detail && <span>{activity.detail}</span>}
          </div>
        )}
        {displayedContours.length > 0 && (
          <div className="laser-profile-legend" aria-hidden="true">
            {displayedContours.map((contour, index) => (
              <span key={`${contour.relative_height}-${index}`}>
                <i style={{ backgroundColor: PROFILE_COLORS[index % PROFILE_COLORS.length] }} />
                {Math.round(Number(contour.relative_height) * 100)}%
              </span>
            ))}
          </div>
        )}
        {!frame && !profileSnapshot && (
          <div className="laser-camera-placeholder">
            <span>{previewEnabled
              ? 'Waiting for camera frame…'
              : `Acquisition stopped · device ${state}`}</span>
          </div>
        )}
      </div>
      {controlError && <div className="laser-inline-error">{controlError}</div>}
      {frameError && <div className="laser-inline-error">{frameError}</div>}
      <BeamProfileSummary progress={progress} />
      {camera && (
        <details className="laser-camera-controls" onToggle={handleCameraControlsToggle}>
          <summary>Camera controls</summary>
          {cameraInfoLoading && (
            <div className="laser-camera-saving">Loading camera settings…</div>
          )}
          {cameraControlsLoaded && !cameraInfoLoading && (
            <div className="laser-camera-parameter-grid">
            {CAMERA_ADVANCED_PARAMETERS.map((parameter) => (
              <label key={parameter.name}>
                <span>{parameter.label}</span>
                <input
                  aria-label={parameter.label}
                  type="number"
                  value={parameters[parameter.name] ?? ''}
                  min={parameter.minValue ?? cameraInfo[parameter.min]}
                  max={parameter.maxValue ?? cameraInfo[parameter.max]}
                  step={parameter.step || 1}
                  disabled={Boolean(parameterBusy)}
                  onChange={(event) => setParameters((current) => ({
                    ...current,
                    [parameter.name]: event.target.value,
                  }))}
                  onBlur={() => writeParameter(parameter.name)}
                />
              </label>
            ))}
            </div>
          )}
          {parameterBusy && <div className="laser-camera-saving">Saving {parameterBusy}…</div>}
        </details>
      )}
      <div className="laser-delta-heading">
        <strong>Centroid diagnostic</strong>
          <span>{progress.score_metric === 'centering_error_px'
            ? 'Absolute camera position is diagnostic · alignment compares contour and aperture centers'
            : 'Display only · automatic alignment minimizes beam roundness error'}</span>
      </div>
      <DeltaVectorChart
        history={history}
        progress={progress}
        tolerance={tolerance}
        hasTranslation={hasTranslation}
      />
    </section>
  );
};

export const ConvergenceChart = ({ history = [], tolerance = 0, hasTranslation = false, objective = 'roundness' }) => {
  const centering = objective === 'centering';
  const observations = history
    .map((item) => ({
      elapsed: Number(item.elapsed_s),
      error: centering ? centeringError(item) : roundnessError(item),
      group: Number(item.actuator_group),
      confirmed: item.confirmed,
    }))
    .filter((item) => Number.isFinite(item.elapsed) && Number.isFinite(item.error));

  if (!observations.length) {
    return (
      <div className="laser-convergence-empty">
        {centering ? 'The first centering measurement will appear here when automatic alignment starts.' : 'The first beam-roundness measurement will appear here when automatic alignment starts.'}
      </div>
    );
  }

  const width = 640;
  const height = 210;
  const margin = { left: 48, right: 14, top: 14, bottom: 34 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const maxTime = Math.max(1, ...observations.map((item) => item.elapsed));
  const maxError = Math.max(1, Number(tolerance) || 0, ...observations.map((item) => item.error));
  const x = (value) => margin.left + (value / maxTime) * plotWidth;
  const y = (value) => margin.top + plotHeight - (value / maxError) * plotHeight;
  const polyline = observations.map((item) => `${x(item.elapsed)},${y(item.error)}`).join(' ');
  const toleranceY = y(Math.max(0, Math.min(maxError, Number(tolerance) || 0)));
  const group1Label = hasTranslation ? 'Near plane · Standa pair 1' : 'Diaphragm 1 · Standa pair 1';
  const group2Label = hasTranslation ? 'Far plane · Standa pair 2' : 'Diaphragm 2 · Standa pair 2';

  return (
    <div className="laser-convergence-wrap">
      <svg
        className="laser-convergence-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={centering ? 'Centering error convergence in pixels' : 'Beam roundness error convergence over elapsed time'}
      >
        {[0, 0.5, 1].map((fraction) => (
          <line
            key={`grid-${fraction}`}
            x1={margin.left}
            x2={width - margin.right}
            y1={margin.top + fraction * plotHeight}
            y2={margin.top + fraction * plotHeight}
            className="laser-chart-grid"
          />
        ))}
        <line x1={margin.left} x2={margin.left} y1={margin.top} y2={height - margin.bottom} className="laser-chart-axis" />
        <line x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} className="laser-chart-axis" />
        <line x1={margin.left} x2={width - margin.right} y1={toleranceY} y2={toleranceY} className="laser-chart-tolerance" />
        <polyline points={polyline} className="laser-chart-line" />
        {observations.map((item, index) => (
          <circle
            key={`${item.elapsed}-${index}`}
            cx={x(item.elapsed)}
            cy={y(item.error)}
            r="4"
            className={`laser-chart-point group-${item.group}`}
          >
            <title>{`${item.elapsed.toFixed(1)} s · ${item.error.toFixed(2)}${centering ? ' px center spread' : '% roundness error'} · ${item.group === 1 ? group1Label : group2Label}${item.confirmed === false ? ' · rejected: not confirmed' : ''}`}</title>
          </circle>
        ))}
        <text x="8" y={margin.top + plotHeight / 2} className="laser-chart-label" transform={`rotate(-90 8 ${margin.top + plotHeight / 2})`}>{centering ? 'Center spread (px)' : 'Roundness error (%)'}</text>
        <text x={margin.left + plotWidth / 2} y={height - 7} className="laser-chart-label">Elapsed time (s)</text>
        <text x={margin.left - 7} y={margin.top + 4} textAnchor="end" className="laser-chart-tick">{maxError.toFixed(1)}</text>
        <text x={margin.left - 7} y={height - margin.bottom + 4} textAnchor="end" className="laser-chart-tick">0</text>
        <text x={margin.left} y={height - margin.bottom + 17} textAnchor="middle" className="laser-chart-tick">0</text>
        <text x={width - margin.right} y={height - margin.bottom + 17} textAnchor="middle" className="laser-chart-tick">{maxTime.toFixed(0)}</text>
      </svg>
      <div className="laser-convergence-legend">
        <span><i className="group-1" />{group1Label}</span>
        <span><i className="group-2" />{group2Label}</span>
        <span><i className="tolerance" />{centering ? 'Centering tolerance' : 'Roundness tolerance'}</span>
      </div>
    </div>
  );
};

export function DeltaVectorChart({
  history = [],
  progress = {},
  tolerance = 0,
  hasTranslation = false,
}) {
  const parseObservation = (item) => {
    const delta = Array.isArray(item?.delta_px) ? item.delta_px : [];
    const deltaX = Number(delta[0]);
    const deltaY = Number(delta[1]);
    if (!Number.isFinite(deltaX) || !Number.isFinite(deltaY)) return null;
    return {
      deltaX,
      deltaY,
      // error_px is retained by the server as a compatibility alias for the
      // roundness score.  The diagnostic magnitude must come from ΔX/ΔY.
      error: Math.hypot(deltaX, deltaY),
      group: Number(item.actuator_group),
    };
  };

  const observations = history.map(parseObservation).filter(Boolean);
  if (!observations.length) {
    const current = parseObservation(progress);
    if (current) observations.push(current);
  }

  const latest = observations[observations.length - 1];
  const safeTolerance = Math.max(0, Number(tolerance) || 0);
  const limit = Math.max(
    5,
    safeTolerance * 1.25,
    ...observations.flatMap((item) => [Math.abs(item.deltaX) * 1.15, Math.abs(item.deltaY) * 1.15])
  );
  const width = 360;
  const height = 310;
  const plotSize = 250;
  const left = 55;
  const top = 14;
  const centreX = left + plotSize / 2;
  const centreY = top + plotSize / 2;
  const scale = plotSize / (2 * limit);
  const x = (value) => centreX + value * scale;
  const y = (value) => centreY - value * scale;
  const trajectory = observations
    .map((item) => `${x(item.deltaX)},${y(item.deltaY)}`)
    .join(' ');
  const group1Label = hasTranslation ? 'Near plane · pair 1' : 'Diaphragm 1 · pair 1';
  const group2Label = hasTranslation ? 'Far plane · pair 2' : 'Diaphragm 2 · pair 2';
  const metric = (value, signed = false) => {
    if (!Number.isFinite(value)) return '— px';
    return `${signed && value >= 0 ? '+' : ''}${value.toFixed(2)} px`;
  };

  return (
    <div className="laser-delta-wrap">
      <div className="laser-delta-metrics" aria-label="Current XY delta values">
        <div><span>ΔX</span><strong>{metric(latest?.deltaX, true)}</strong></div>
        <div><span>ΔY</span><strong>{metric(latest?.deltaY, true)}</strong></div>
        <div><span>|Δ|</span><strong>{metric(latest?.error)}</strong></div>
      </div>
      <svg
        className="laser-delta-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="XY delta vector and trajectory centred on zero"
      >
        <rect x={left} y={top} width={plotSize} height={plotSize} className="laser-delta-background" />
        {[-0.5, 0.5].map((fraction) => (
          <React.Fragment key={fraction}>
            <line x1={x(limit * fraction)} x2={x(limit * fraction)} y1={top} y2={top + plotSize} className="laser-chart-grid" />
            <line x1={left} x2={left + plotSize} y1={y(limit * fraction)} y2={y(limit * fraction)} className="laser-chart-grid" />
          </React.Fragment>
        ))}
        <line x1={centreX} x2={centreX} y1={top} y2={top + plotSize} className="laser-delta-zero" />
        <line x1={left} x2={left + plotSize} y1={centreY} y2={centreY} className="laser-delta-zero" />
        <circle cx={centreX} cy={centreY} r={safeTolerance * scale} className="laser-chart-tolerance" />
        {observations.length > 1 && <polyline points={trajectory} className="laser-chart-line" />}
        {latest && (
          <line
            x1={centreX}
            y1={centreY}
            x2={x(latest.deltaX)}
            y2={y(latest.deltaY)}
            className="laser-delta-vector"
          />
        )}
        {observations.map((item, index) => (
          <circle
            key={`${item.deltaX}-${item.deltaY}-${index}`}
            cx={x(item.deltaX)}
            cy={y(item.deltaY)}
            r={index === observations.length - 1 ? 6 : 4}
            className={`laser-chart-point group-${item.group} ${index === observations.length - 1 ? 'current' : ''}`}
          >
            <title>{`ΔX ${item.deltaX.toFixed(2)} px · ΔY ${item.deltaY.toFixed(2)} px · ${item.group === 1 ? group1Label : group2Label}`}</title>
          </circle>
        ))}
        {!observations.length && (
          <text x={centreX} y={centreY - 12} className="laser-delta-empty">
            Waiting for first point comparison
          </text>
        )}
        <text x={centreX} y={height - 7} className="laser-chart-label">ΔX (px)</text>
        <text x="13" y={centreY} className="laser-chart-label" transform={`rotate(-90 13 ${centreY})`}>ΔY (px)</text>
        <text x={left} y={top + plotSize + 16} textAnchor="middle" className="laser-chart-tick">{(-limit).toFixed(1)}</text>
        <text x={centreX} y={top + plotSize + 16} textAnchor="middle" className="laser-chart-tick">0</text>
        <text x={left + plotSize} y={top + plotSize + 16} textAnchor="middle" className="laser-chart-tick">{limit.toFixed(1)}</text>
        <text x={left - 7} y={top + 4} textAnchor="end" className="laser-chart-tick">{limit.toFixed(1)}</text>
        <text x={left - 7} y={centreY + 4} textAnchor="end" className="laser-chart-tick">0</text>
        <text x={left - 7} y={top + plotSize + 4} textAnchor="end" className="laser-chart-tick">{(-limit).toFixed(1)}</text>
      </svg>
      <div className="laser-convergence-legend laser-delta-legend">
        <span><i className="group-1" />{group1Label}</span>
        <span><i className="group-2" />{group2Label}</span>
        <span><i className="tolerance" />{safeTolerance.toFixed(1)} px display guide</span>
      </div>
    </div>
  );
}

const CompactActuator = ({ actuator, disabled, active, lockReason, onMove }) => {
  const [step, setStep] = useState(1);
  const position = Number(actuator.position);
  const visualState = actuatorVisualState(actuator);
  const disconnected = visualState === 'disconnected';
  const ready = visualState === 'ready';
  const badge = disconnected ? 'DISCONNECTED' : (ready ? (active ? 'SELECTED' : 'READY') : 'NOT READY');
  const move = (direction) => {
    if (Number.isFinite(position)) onMove(actuator, position + direction * step);
  };

  return (
    <div
      className={`laser-actuator-row ${ready ? 'active' : 'locked'} ${active ? 'selected' : ''} ${disconnected ? 'disconnected' : ''}`}
      title={actuator.hardware_lifecycle_status || lockReason || ''}
    >
      <span className={`laser-state-dot state-${visualState}`} />
      <strong title={actuator.device}>{actuator.role}</strong>
      <span className={`laser-mount-lock ${ready ? 'active' : (disconnected ? 'disconnected' : 'locked')}`}>
        {badge}
      </span>
      <span className="laser-position">
        {Number.isFinite(position) ? position.toFixed(3) : '—'}
      </span>
      <button
        type="button"
        aria-label={`Decrease ${actuator.role} by ${step}`}
        onClick={() => move(-1)}
        disabled={disabled}
      >−</button>
      <label className="laser-actuator-step">
        <span>Step</span>
        <select
          aria-label={`${actuator.role} step size`}
          value={step}
          onChange={(event) => setStep(Number(event.target.value))}
        >
          {[0.5, 1, 2, 5].map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
      </label>
      <button
        type="button"
        aria-label={`Increase ${actuator.role} by ${step}`}
        onClick={() => move(1)}
        disabled={disabled}
      >+</button>
    </div>
  );
};

const CompactManualAxis = ({ hardware, axis, disabled, onMove }) => {
  const [step, setStep] = useState(1);
  const position = Number(axis.position);
  const visualState = actuatorVisualState(hardware);
  const disconnected = visualState === 'disconnected';
  const move = (direction) => {
    if (Number.isFinite(position)) {
      onMove(hardware, axis.axis, position + direction * step);
    }
  };

  return (
    <div className={`laser-manual-axis ${disconnected ? 'disconnected' : ''}`}>
      <span className={`laser-state-dot state-${visualState}`} />
      <strong>Axis {axis.axis}</strong>
      <span className="laser-position">
        {Number.isFinite(position) ? position.toFixed(3) : '—'}
      </span>
      <button type="button" onClick={() => move(-1)} disabled={disabled || disconnected}>−</button>
      <select
        value={step}
        disabled={disabled || disconnected}
        onChange={(event) => setStep(Number(event.target.value))}
      >
        {[0.1, 0.5, 1, 2, 5, 10].map((value) => (
          <option key={value} value={value}>{value}</option>
        ))}
      </select>
      <button type="button" onClick={() => move(1)} disabled={disabled || disconnected}>+</button>
    </div>
  );
};

const ManualDevice = ({ hardware, disabled, onMove }) => (
  <section className={`laser-panel laser-manual-device ${hardware.disconnected ? 'disconnected' : ''}`}>
    <div className="laser-section-heading">
      <strong>{hardware.role}</strong>
      <span>{hardware.device} · {String(hardware.state || 'UNKNOWN').split('.').pop()}</span>
    </div>
    {(hardware.axes || []).map((axis) => (
      <CompactManualAxis
        key={axis.axis}
        hardware={hardware}
        axis={axis}
        disabled={disabled || !hardware.move_supported}
        onMove={onMove}
      />
    ))}
  </section>
);

export {
  CompactActuator, CompactManualAxis, ManualDevice,
};
