import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import './LaserPointingController.css';

const API_BASE = (process.env.REACT_APP_API_BASE || '/api').replace(/\/$/, '');

export const pointNumber = (name) => {
  const match = String(name || '').match(/^point(\d+)$/i);
  return match ? Number(match[1]) : null;
};

export const actuatorGroupForPoint = (name) => {
  const number = pointNumber(name);
  if (number >= 1 && number <= 3) return 1;
  if (number >= 4 && number <= 6) return 2;
  return 0;
};

export const actuatorGroupForRole = (role, groups = {}) => {
  const actuatorGroups = Object.entries(groups)
    .filter(([name, roles]) => /^actuators/i.test(name) && Array.isArray(roles));
  const index = actuatorGroups.findIndex(([, roles]) => roles.includes(role));
  return index < 0 ? 0 : index + 1;
};

export const actuatorVisualState = (actuator = {}) => {
  const connection = String(actuator.hardware_connection_state || '').toUpperCase();
  const state = String(actuator.state || 'UNKNOWN').toUpperCase().split('.').pop();
  if (actuator.disconnected || [
    'DISCONNECTED', 'POWER_OFF', 'POWER_STATUS_UNAVAILABLE',
  ].includes(connection) || ['FAULT', 'OFF', 'UNKNOWN', 'UNREACHABLE'].includes(state)) {
    return 'disconnected';
  }
  if (actuator.ready
    || connection === 'READY'
    || String(actuator.initialization_state || '').toUpperCase() === 'SUCCEEDED') {
    return 'ready';
  }
  if (state === 'MOVING') return 'moving';
  return 'standby';
};

export const pointAperture = (settings = {}) => {
  const candidates = Object.entries(settings)
    .filter(([role]) => role.includes('CrimpingDiaphragm'))
    .map(([, value]) => Number(value))
    .filter((value) => Number.isFinite(value) && value >= 0);
  // The inactive diaphragm is parked at its measured open plateau. The
  // smaller opening is therefore the diaphragm that defines this point.
  return candidates.length ? Math.min(...candidates) : null;
};

const pointSensitivity = (name) => {
  const number = pointNumber(name);
  if ([1, 4].includes(number)) return 'Wide';
  if ([2, 5].includes(number)) return 'Medium';
  if ([3, 6].includes(number)) return 'Fine';
  return 'Preset';
};

const formatOpticalValue = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '—';
  return Number.isInteger(numeric) ? numeric.toFixed(0) : numeric.toFixed(1);
};

const finiteNumber = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

export const roundnessError = (observation = {}) => (
  finiteNumber(observation.roundness_error_pct)
  ?? finiteNumber(observation.error_px)
);

export const formatOpticalStatusValue = (role, value) => {
  const normalized = String(role || '').toLowerCase().replace(/[ -]/g, '_');
  if (/shutter|flipper/.test(normalized)) {
    const state = String(value || '').toUpperCase();
    if (state === 'UP_BLOCKED') return 'UP · BLOCKED';
    if (state === 'DOWN_CLEAR') return 'DOWN · CLEAR';
    if (state === 'RIGHT') return 'DOWN';
    if (state === 'LEFT') return 'UP · BLOCKED';
    if (['BETWEEN', 'CONFLICT', 'UNKNOWN'].includes(state)) return state;
  }
  const numeric = finiteNumber(value);
  if (numeric === null) return '—';
  if (/shutter|flipper/.test(normalized)) {
    if (Math.abs(numeric + 1) <= 0.2) return '−1';
    if (Math.abs(numeric - 1) <= 0.2) return '+1';
    return 'UNKNOWN';
  }
  if (/diaphragm|halfwaveplate|half_wave_plate|lambda/.test(normalized)) {
    return `${Number.isInteger(numeric) ? numeric.toFixed(0) : numeric.toFixed(1)}%`;
  }
  return formatOpticalValue(numeric);
};

const stateName = (value) => String(value || 'UNKNOWN').toUpperCase().split('.').pop();

const componentVisualState = (component = {}) => {
  const state = stateName(component.state);
  if (component.disconnected || ['FAULT', 'OFF', 'UNKNOWN', 'UNREACHABLE'].includes(state)) {
    return 'disconnected';
  }
  if (state === 'MOVING') return 'moving';
  if (component.ready || ['ON', 'RUNNING'].includes(state)) return 'ready';
  return actuatorVisualState(component);
};

export const ComponentStatusPanel = ({ snapshot = {} }) => {
  const cards = [];
  const camera = snapshot.camera || {};
  if (camera.device) {
    cards.push({
      key: 'camera',
      caption: 'Camera',
      indicators: [{
        label: stateName(camera.state),
        visualState: componentVisualState(camera),
        title: camera.device,
      }],
    });
  }

  Object.entries(snapshot.groups || {})
    .filter(([name, roles]) => /^actuators/i.test(name) && Array.isArray(roles))
    .forEach(([name, roles], index) => {
      const indicators = roles.map((role) => {
        const actuator = (snapshot.actuators || []).find((item) => item.role === role) || {};
        return {
          label: /x/i.test(role) ? 'X' : (/y/i.test(role) ? 'Y' : role),
          visualState: componentVisualState(actuator),
          title: actuator.device || role,
        };
      });
      cards.push({ key: name, caption: `Standa ${index + 1}`, indicators });
    });

  (snapshot.other_devices || snapshot.diaphragms || []).forEach((device) => {
    cards.push({
      key: device.role,
      caption: device.role,
      value: formatOpticalStatusValue(
        device.role,
        device.control_type === 'flipper'
          ? device.commanded_flipper_state : device.position,
      ),
      title: device.device,
    });
  });

  (snapshot.manual_devices || []).forEach((device) => {
    const value = (device.axes || []).map((axis) => (
      `A${axis.axis} ${formatOpticalStatusValue(device.role, axis.position)}`
    )).join(' · ') || stateName(device.state);
    cards.push({
      key: device.role,
      caption: device.role,
      value,
      title: device.device,
    });
  });

  return (
    <section className="laser-component-status-panel" aria-label="Main components live status">
      <div className="laser-section-heading">
        <strong>Main components · live status</strong>
        <span>Readback / flipper command</span>
      </div>
      <div className="laser-component-status-grid">
        {cards.map((card) => (
          <div className="laser-component-status-card" key={card.key} title={card.title || ''}>
            <span className="laser-component-status-caption">{card.caption}</span>
            {card.indicators ? (
              <span className="laser-component-indicators">
                {card.indicators.map((indicator) => (
                  <span key={`${card.key}-${indicator.label}`} title={indicator.title}>
                    <i className={`laser-state-dot state-${indicator.visualState}`} />
                    {indicator.label}
                  </span>
                ))}
              </span>
            ) : (
              <strong className="laser-component-status-value">{card.value}</strong>
            )}
          </div>
        ))}
      </div>
    </section>
  );
};

const OpticalPointState = ({ point, snapshot, transition }) => {
  if (!point) return null;
  const settings = point.settings || {};
  const diaphragmSettings = Object.entries(settings)
    .filter(([role]) => /diaphragm/i.test(role));
  const stageSetting = Object.entries(settings)
    .find(([role]) => /translationstage|delayline|(^|_)dl($|_)/i.test(role));
  const liveOptics = snapshot.other_devices || snapshot.diaphragms || [];
  const before = transition?.name === point.name ? transition.before : {};

  const currentForRole = (role) => {
    const optic = liveOptics.find((device) => device.role === role);
    if (optic) return optic.position;
    const hardware = (snapshot.manual_devices || []).find((device) => device.role === role);
    if (!hardware) return null;
    const configured = settings[role];
    const axisNumber = Array.isArray(configured) ? Number(configured[0]) : null;
    const axis = (hardware.axes || []).find((item) => axisNumber === null
      || Number(item.axis) === axisNumber);
    return axis?.position ?? null;
  };

  return (
    <div className="laser-point-state" aria-label={`${point.name} optical state`}>
      <div className="laser-point-state-heading">
        <strong>Point {point.number || point.name} optical state</strong>
        <span>Previous → selected target</span>
      </div>
      <div className="laser-aperture-list">
        {diaphragmSettings.map(([role, targetValue]) => {
          const target = Number(targetValue);
          const current = currentForRole(role);
          const previous = before[role] ?? current;
          const openingDiameter = Number.isFinite(target)
            ? Math.max(4, Math.min(88, Math.sqrt(Math.max(0, target) / 100) * 88))
            : 4;
          const openingState = target >= 99.5
            ? 'Fully open' : (target <= 0.5 ? 'Closed' : 'Partly open');
          return (
            <div className="laser-aperture-item" key={role}>
              <div
                className="laser-aperture-visual"
                style={{ '--opening-size': `${openingDiameter}%` }}
                role="img"
                aria-label={`${role} target aperture ${formatOpticalValue(target)}% open`}
              >
                <span />
              </div>
              <div>
                <strong>{role}</strong>
                <span>{openingState} · {formatOpticalValue(target)}%</span>
                <small>
                  {formatOpticalValue(previous)}% → {formatOpticalValue(target)}%
                  {Number.isFinite(Number(current))
                    && Math.abs(Number(current) - target) < 0.01 ? ' · reached' : ''}
                </small>
              </div>
            </div>
          );
        })}
        {stageSetting && (() => {
          const [role, configured] = stageSetting;
          const axis = Array.isArray(configured) ? Number(configured[0]) : null;
          const target = Array.isArray(configured) ? Number(configured[1]) : Number(configured);
          const current = currentForRole(role);
          const previous = before[role] ?? current;
          return (
            <div className="laser-dl-position">
              <div className="laser-dl-track" aria-hidden="true"><span /></div>
              <div>
                <strong>DL position</strong>
                <span>{formatOpticalValue(previous)} → {formatOpticalValue(target)}</span>
                <small>{role}{axis !== null ? ` · axis ${axis}` : ''}</small>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
};

const CAMERA_NUMERIC_PARAMETERS = [
  {
    name: 'center_gravity_threshold',
    label: 'Threshold CG',
    minValue: 0,
    maxValue: 255,
  },
  { name: 'offsetX', label: 'Offset X' },
  { name: 'offsetY', label: 'Offset Y' },
  { name: 'exposure_time', label: 'Exposure (µs)', min: 'exposure_min', max: 'exposure_max', step: 'any' },
  { name: 'gain', label: 'Gain', min: 'gain_min', max: 'gain_max', step: 'any' },
  { name: 'width', label: 'Width', min: 'width_min', max: 'width_max' },
  { name: 'height', label: 'Height', min: 'height_min', max: 'height_max' },
];

const CAMERA_PARAMETER_NAMES = CAMERA_NUMERIC_PARAMETERS.map(({ name }) => name);

export const laserSnapshotErrorMessage = (error) => {
  const message = String(error?.message || error || 'Snapshot failed');
  if (/API_CommandTimedOut|not able to acquire serialization/i.test(message)) {
    return 'LaserPointing controller is busy; retrying automatically…';
  }
  return message;
};

const PROFILE_COLORS = [
  '#39d0ff', '#35e0a1', '#7be04b', '#c8e43d', '#ffd23d',
  '#ff9f31', '#ff6b45', '#f0447d', '#c05cff',
];

const signedMotorDelta = (value) => {
  const numeric = finiteNumber(value);
  if (numeric === null) return '—';
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(2)}`;
};

export const alignmentActivityText = (progress = {}) => {
  const phase = String(progress.phase || '').toLowerCase();
  const point = String(progress.point || progress.measured_point || '').replace(/^point/i, 'point ');
  if (!phase) return null;
  if (phase === 'starting') {
    return { title: 'Preparing automatic alignment', detail: 'Checking camera and optical sequence' };
  }
  if (phase === 'applying_point') {
    const role = progress.optical_role ? ` · ${progress.optical_role}` : '';
    const target = progress.optical_target !== undefined
      ? ` → ${formatOpticalValue(progress.optical_target)}` : '';
    return { title: `Moving optics to ${point || 'the next point'}`, detail: `${role}${target}`.replace(/^ · /, '') };
  }
  if (phase === 'moving_actuators') {
    const roles = Array.isArray(progress.actuator_roles) ? progress.actuator_roles : [];
    const deltas = Array.isArray(progress.move_delta) ? progress.move_delta : [];
    const changes = roles.map((role, index) => `${role} ${signedMotorDelta(deltas[index])}`);
    return {
      title: `Adjusting ${progress.group || 'Standa pair'}`,
      detail: changes.filter(Boolean).join(' · ') || `Candidate ${JSON.stringify(progress.actuator_position || [])}`,
    };
  }
  if (phase === 'capturing_profiles') {
    return {
      title: `Capturing ${point || 'beam'} profile`,
      detail: `Frame ${progress.sample || '?'} of ${progress.samples || '?'}`,
    };
  }
  if (phase === 'calculating_profiles') {
    return {
      title: `Calculating profiles at ${point || 'current point'}`,
      detail: 'Fitting nine iso-intensity contours from the outer beam to the core',
    };
  }
  if (phase === 'measuring') {
    const error = roundnessError(progress);
    return {
      title: `${point || 'Beam'} profiles measured`,
      detail: error === null
        ? 'Evaluating roundness'
        : `Roundness error ${error.toFixed(2)}% · ${progress.group || 'active pair'}`,
    };
  }
  if (phase === 'verifying') {
    return { title: 'Verifying both optical planes', detail: `Motor step ${formatOpticalValue(progress.motor_step)}` };
  }
  if (phase === 'finished') return { title: 'Alignment converged', detail: 'Final verification passed' };
  if (phase === 'not_converged') return { title: 'Alignment did not converge', detail: 'Best measured positions were retained' };
  if (phase === 'laser_not_visible') return { title: 'Laser not visible', detail: progress.message || 'Search stopped safely' };
  if (phase === 'cancelled') return { title: 'Alignment stopped', detail: 'No further movement will be issued' };
  if (phase === 'error') return { title: 'Alignment error', detail: progress.message || 'Search stopped' };
  return { title: progress.message || phase.replace(/_/g, ' '), detail: '' };
};

const BeamProfileSummary = ({ progress = {} }) => {
  const contours = Array.isArray(progress?.beam_shape?.contours)
    ? progress.beam_shape.contours : [];
  if (!contours.length) return null;
  return (
    <div className="laser-profile-summary" aria-label="Beam profiles at multiple thresholds">
      <div className="laser-profile-heading">
        <strong>Beam profiles · threshold sweep</strong>
        <span>{contours.length} fitted contours</span>
      </div>
      <div className="laser-profile-levels">
        {contours.map((contour, index) => (
          <div key={`${contour.relative_height}-${index}`}>
            <i style={{ backgroundColor: PROFILE_COLORS[index % PROFILE_COLORS.length] }} />
            <span>{`${Math.round(Number(contour.relative_height) * 100)}%`}</span>
            <strong>{`${finiteNumber(contour.axis_roundness_pct)?.toFixed(1) || '—'}% round`}</strong>
            <small>{`r ${finiteNumber(contour.radius_px)?.toFixed(1) || '—'} px`}</small>
          </div>
        ))}
      </div>
    </div>
  );
};

export const measuredProfileSnapshot = (progress = {}) => {
  const shape = progress?.beam_shape;
  const dataUrl = typeof shape?.preview_data_url === 'string'
    && shape.preview_data_url.startsWith('data:image/png;base64,')
    ? shape.preview_data_url : '';
  if (!dataUrl) return null;
  const centroid = Array.isArray(shape.preview_centroid)
    ? {
      X: finiteNumber(shape.preview_centroid[0]),
      Y: finiteNumber(shape.preview_centroid[1]),
    }
    : null;
  return {
    dataUrl,
    centroid: centroid?.X !== null && centroid?.Y !== null ? centroid : null,
    point: progress.measured_point || progress.point || '',
  };
};

const drawBeamOverlays = (context, width, marker, contours) => {
  const x = finiteNumber(marker?.X);
  const y = finiteNumber(marker?.Y);
  if (x !== null && y !== null) {
    context.strokeStyle = '#ff3b30';
    context.lineWidth = 2;
    context.beginPath();
    context.arc(x, y, 10, 0, Math.PI * 2);
    context.moveTo(x - 15, y);
    context.lineTo(x + 15, y);
    context.moveTo(x, y - 15);
    context.lineTo(x, y + 15);
    context.stroke();
  }

  contours.forEach((contour, index) => {
    const centreX = finiteNumber(contour?.centre?.[0]);
    const centreY = finiteNumber(contour?.centre?.[1]);
    const radius = finiteNumber(contour?.radius_px);
    const axisRatio = Math.max(0.05, Math.min(1, (finiteNumber(contour?.axis_roundness_pct) ?? 100) / 100));
    if (centreX === null || centreY === null || radius === null || radius <= 0) return;
    const major = radius / Math.sqrt(axisRatio);
    const minor = radius * Math.sqrt(axisRatio);
    const angle = ((finiteNumber(contour?.major_axis_angle_deg) ?? 0) * Math.PI) / 180;
    context.save();
    context.strokeStyle = PROFILE_COLORS[index % PROFILE_COLORS.length];
    context.lineWidth = Math.max(1.3, width / 500);
    context.setLineDash(index % 2 ? [5, 3] : []);
    context.beginPath();
    context.ellipse(centreX, centreY, major, minor, angle, 0, Math.PI * 2);
    context.stroke();
    context.restore();
  });
};

export const CameraPreview = ({
  camera,
  enabled = true,
  state = 'UNKNOWN',
  history = [],
  progress = {},
  tolerance = 0,
  hasTranslation = false,
  onRefresh,
}) => {
  const canvasRef = useRef(null);
  const frameRequestInFlight = useRef(false);
  const [frame, setFrame] = useState(null);
  const [centroid, setCentroid] = useState(null);
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
        `${API_BASE}/camera/${encodeURIComponent(camera)}/image`,
        { credentials: 'include' }
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        if (response.status === 409 && payload.grabbing === false) {
          setFrame(null);
          setCentroid(null);
          setFrameError('');
          return;
        }
        throw new Error(payload.error || `Image request failed (${response.status})`);
      }
      setFrame(payload.image);
      setCentroid(payload.cg_position || null);
      setFrameError('');
    } catch (requestError) {
      setFrameError(requestError.message);
    } finally {
      frameRequestInFlight.current = false;
    }
  }, [camera]);

  useEffect(() => {
    if (!previewEnabled) {
      setFrame(null);
      setCentroid(null);
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

    if (profileSnapshot && beamContours.length) {
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
    drawBeamOverlays(context, width, centroid, []);
    return undefined;
  }, [frame, centroid, beamContours, profileSnapshot]);

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
      if (cameraControlsLoaded) await loadCameraInfo();
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
        {profileSnapshot && beamContours.length > 0 && (
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
        {beamContours.length > 0 && (
          <div className="laser-profile-legend" aria-hidden="true">
            {beamContours.map((contour, index) => (
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
            {CAMERA_NUMERIC_PARAMETERS.map((parameter) => (
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
        <span>Display only · automatic alignment minimizes beam roundness error</span>
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

export const ConvergenceChart = ({ history = [], tolerance = 0, hasTranslation = false }) => {
  const observations = history
    .map((item) => ({
      elapsed: Number(item.elapsed_s),
      error: roundnessError(item),
      group: Number(item.actuator_group),
    }))
    .filter((item) => Number.isFinite(item.elapsed) && Number.isFinite(item.error));

  if (!observations.length) {
    return (
      <div className="laser-convergence-empty">
        The first beam-roundness measurement will appear here when automatic alignment starts.
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
        aria-label="Beam roundness error convergence over elapsed time"
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
            <title>{`${item.elapsed.toFixed(1)} s · ${item.error.toFixed(2)}% roundness error · ${item.group === 1 ? group1Label : group2Label}`}</title>
          </circle>
        ))}
        <text x="8" y={margin.top + plotHeight / 2} className="laser-chart-label" transform={`rotate(-90 8 ${margin.top + plotHeight / 2})`}>Roundness error (%)</text>
        <text x={margin.left + plotWidth / 2} y={height - 7} className="laser-chart-label">Elapsed time (s)</text>
        <text x={margin.left - 7} y={margin.top + 4} textAnchor="end" className="laser-chart-tick">{maxError.toFixed(1)}</text>
        <text x={margin.left - 7} y={height - margin.bottom + 4} textAnchor="end" className="laser-chart-tick">0</text>
        <text x={margin.left} y={height - margin.bottom + 17} textAnchor="middle" className="laser-chart-tick">0</text>
        <text x={width - margin.right} y={height - margin.bottom + 17} textAnchor="middle" className="laser-chart-tick">{maxTime.toFixed(0)}</text>
      </svg>
      <div className="laser-convergence-legend">
        <span><i className="group-1" />{group1Label}</span>
        <span><i className="group-2" />{group2Label}</span>
        <span><i className="tolerance" />Roundness tolerance</span>
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

const DiaphragmControl = ({ diaphragm, disabled, onMove, onStop }) => {
  const position = Number(diaphragm.position);
  const [target, setTarget] = useState(Number.isFinite(position) ? String(position) : '');
  const [step, setStep] = useState(1);
  const visualState = actuatorVisualState(diaphragm);
  const disconnected = visualState === 'disconnected';
  const controlsDisabled = disabled || disconnected || !diaphragm.move_supported;
  const unit = diaphragm.unit || '%';
  const isHalfWavePlate = diaphragm.control_type === 'half_wave_plate';
  const isFlipper = diaphragm.control_type === 'flipper';
  const controlTitle = isHalfWavePlate
    ? `λ/2 plate · ${diaphragm.role}`
    : (isFlipper ? `Camera flipper · ${diaphragm.role}` : diaphragm.role);
  const presetLabel = isHalfWavePlate
    ? 'λ/2 presets' : (isFlipper ? 'Flipper positions' : 'Opening presets');
  const formatPreset = (value) => (
    Number.isInteger(Number(value)) ? Number(value).toFixed(0) : String(Number(value))
  );

  useEffect(() => {
    if (Number.isFinite(position)) setTarget(String(position));
  }, [position]);

  const moveTo = (value) => {
    const numericTarget = Number(value);
    if (Number.isFinite(numericTarget)) onMove(diaphragm, numericTarget);
  };

  if (isFlipper) {
    return (
      <section className={`laser-panel laser-diaphragm-card ${disconnected ? 'disconnected' : ''}`}>
        <div className="laser-section-heading">
          <strong>{controlTitle}</strong>
          <span>{diaphragm.device} · {String(diaphragm.state || 'UNKNOWN').split('.').pop()}</span>
        </div>
        <div className="laser-diaphragm-readback">
          <span className={`laser-state-dot state-${visualState}`} />
          <span>Last completed command</span>
          <strong>{formatOpticalStatusValue(diaphragm.role, diaphragm.commanded_flipper_state)}</strong>
        </div>
        <div className="laser-diaphragm-controls laser-flipper-controls">
          <button type="button" onClick={() => moveTo(-1)} disabled={controlsDisabled}>
            −1 · Raise / block
          </button>
          <button type="button" onClick={() => moveTo(1)} disabled={controlsDisabled}>
            +1 · Lower / clear
          </button>
          <button type="button" className="stop" onClick={() => onStop(diaphragm)}
            disabled={disabled || disconnected || !diaphragm.stop_supported}>
            Stop motion
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className={`laser-panel laser-diaphragm-card ${disconnected ? 'disconnected' : ''}`}>
      <div className="laser-section-heading">
        <strong>{controlTitle}</strong>
        <span>
          {diaphragm.friendly_name ? `${diaphragm.friendly_name} · ` : ''}
          {diaphragm.device} · {String(diaphragm.state || 'UNKNOWN').split('.').pop()}
        </span>
      </div>
      <div className="laser-diaphragm-readback">
        <span className={`laser-state-dot state-${visualState}`} />
        <span>Current position</span>
        <strong>{Number.isFinite(position) ? `${position.toFixed(2)} ${unit}` : 'Unavailable'}</strong>
      </div>
      <div className="laser-diaphragm-controls">
        <label>
          Target ({unit})
          <input
            type="number"
            aria-label={`${diaphragm.role} target`}
            value={target}
            min={diaphragm.minimum ?? undefined}
            max={diaphragm.maximum ?? undefined}
            step="any"
            disabled={controlsDisabled}
            onChange={(event) => setTarget(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') moveTo(target);
            }}
          />
        </label>
        <button
          type="button"
          aria-label={`Move ${diaphragm.role} to target`}
          onClick={() => moveTo(target)}
          disabled={controlsDisabled}
        >
          Move to target
        </button>
        <label>
          Step ({unit})
          <select
            aria-label={`${diaphragm.role} step`}
            value={step}
            disabled={controlsDisabled}
            onChange={(event) => setStep(Number(event.target.value))}
          >
            {[0.1, 0.5, 1, 2, 5, 10].map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          aria-label={`Decrease ${diaphragm.role}`}
          onClick={() => moveTo(position - step)}
          disabled={controlsDisabled || !Number.isFinite(position)}
        >
          −
        </button>
        <button
          type="button"
          aria-label={`Increase ${diaphragm.role}`}
          onClick={() => moveTo(position + step)}
          disabled={controlsDisabled || !Number.isFinite(position)}
        >
          +
        </button>
        <button
          type="button"
          className="stop"
          onClick={() => onStop(diaphragm)}
          disabled={disabled || disconnected || !diaphragm.stop_supported}
        >
          Stop motion
        </button>
      </div>
      {(diaphragm.preset_positions || []).length > 0 && (
        <div className="laser-other-presets">
          <strong>{presetLabel} ({unit})</strong>
          <div>
            {diaphragm.preset_positions.map((preset) => (
              <button
                type="button"
                key={preset}
                className={Number.isFinite(position) && Math.abs(position - Number(preset)) < 0.01
                  ? 'selected' : ''}
                aria-label={`Set ${diaphragm.role} to ${formatPreset(preset)} ${unit}`}
                aria-pressed={Number.isFinite(position)
                  && Math.abs(position - Number(preset)) < 0.01}
                onClick={() => moveTo(preset)}
                disabled={controlsDisabled}
              >
                {formatPreset(preset)}{unit}
              </button>
            ))}
          </div>
        </div>
      )}
      {!diaphragm.move_supported && (
        <div className="laser-inline-error">This device does not expose move_axis_abs.</div>
      )}
    </section>
  );
};

const LaserPointingController = ({ deviceName }) => {
  const [snapshot, setSnapshot] = useState(null);
  const [config, setConfig] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('automatic');
  const [pointTransition, setPointTransition] = useState(null);
  const snapshotRequestInFlight = useRef(false);

  const loadSnapshot = useCallback(async () => {
    if (snapshotRequestInFlight.current) return;
    snapshotRequestInFlight.current = true;
    try {
      const response = await fetch(
        `${API_BASE}/laser-pointing/${encodeURIComponent(deviceName)}/snapshot`,
        { credentials: 'include' }
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `Snapshot failed (${response.status})`);
      }
      setSnapshot(payload.snapshot);
      setConfig((current) => current || payload.snapshot.automatic_search?.config || {});
      setError('');
    } catch (requestError) {
      setError(laserSnapshotErrorMessage(requestError));
    } finally {
      snapshotRequestInFlight.current = false;
    }
  }, [deviceName]);

  useEffect(() => {
    loadSnapshot();
    const timer = setInterval(loadSnapshot, 1500);
    return () => clearInterval(timer);
  }, [loadSnapshot]);

  const executeDeviceCommand = async (targetDevice, command, args, busyLabel) => {
    setBusy(busyLabel);
    setError('');
    try {
      const body = args === undefined ? {} : { args };
      const response = await fetchWithHardwareApproval(
        `${API_BASE}/device/${encodeURIComponent(targetDevice)}/command/${command}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(body),
        }
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `${command} failed (${response.status})`);
      }
      await loadSnapshot();
      return true;
    } catch (requestError) {
      setError(requestError.message);
      return false;
    } finally {
      setBusy('');
    }
  };

  const execute = (command, args, busyLabel) => (
    executeDeviceCommand(deviceName, command, args, busyLabel)
  );

  const applyPoint = async (name) => {
    if (!snapshot?.capabilities?.apply_point) {
      setError('Restart DS_LaserPointing to activate controller-owned point presets.');
      return;
    }
    await execute('apply_controller_point', name, `Applying ${name}`);
  };

  const activateOpticalPoint = (point) => {
    const before = {};
    const liveOptics = snapshot?.other_devices || snapshot?.diaphragms || [];
    liveOptics.forEach((device) => {
      before[device.role] = device.position;
    });
    (snapshot?.manual_devices || []).forEach((device) => {
      const configured = point.settings?.[device.role];
      const axisNumber = Array.isArray(configured) ? Number(configured[0]) : null;
      const axis = (device.axes || []).find((item) => axisNumber === null
        || Number(item.axis) === axisNumber);
      if (axis) before[device.role] = axis.position;
    });
    setPointTransition({ name: point.name, before });
    applyPoint(point.name);
  };

  const startSearch = () => {
    if (!snapshot?.capabilities?.automatic_search) {
      setError('Restart DS_LaserPointing to activate automatic search.');
      return;
    }
    const schedule = [
      Number(config.step_coarse),
      Number(config.step_middle),
      Number(config.step_fine),
    ];
    if (!(schedule[0] > schedule[1] && schedule[1] > schedule[2])) {
      setError('Coarse, middle and fine steps must be strictly decreasing.');
      return;
    }
    execute(
      'start_automatic_search',
      JSON.stringify({
        ...config,
        step_schedule: schedule,
        initial_step: schedule[0],
        minimum_step: schedule[2],
        roundness_tolerance_pct: finiteNumber(config.roundness_tolerance_pct) ?? 7,
      }),
      'Starting automatic search'
    );
  };

  const moveActuator = async (actuator, target) => {
    if (actuatorVisualState(actuator) !== 'ready') {
      setError(`${actuator.role} is not ready for movement.`);
      return;
    }
    await executeDeviceCommand(
      actuator.device,
      'move_axis_abs',
      Number(target),
      `Moving ${actuator.role}`
    );
  };

  const moveManualAxis = async (hardware, axis, target) => {
    await executeDeviceCommand(
      hardware.device,
      'move_axis',
      [Number(axis), Number(target)],
      `Moving ${hardware.role} axis ${axis}`
    );
  };

  const moveOtherDevice = async (hardware, target) => {
    await executeDeviceCommand(
      hardware.device,
      'move_axis_abs',
      Number(target),
      `Moving ${hardware.role} to ${Number(target)}`
    );
  };

  const stopOtherDevice = async (hardware) => {
    await executeDeviceCommand(
      hardware.device,
      'stop_movement',
      undefined,
      `Stopping ${hardware.role}`
    );
  };

  const numberedPoints = useMemo(() => Object.entries(snapshot?.rules || {})
    .map(([name, settings]) => ({ name, number: pointNumber(name), settings }))
    .filter((point) => point.number !== null)
    .sort((a, b) => a.number - b.number), [snapshot]);
  const workingPoint = Object.entries(snapshot?.rules || {})
    .find(([name]) => pointNumber(name) === null);
  const hasTranslation = numberedPoints.some(
    (point) => Object.prototype.hasOwnProperty.call(point.settings, 'TranslationStage1')
  );
  const searchStatus = snapshot?.automatic_search?.status || 'loading';
  const running = ['running', 'stopping'].includes(searchStatus);
  const progress = snapshot?.automatic_search?.progress || {};
  const pointApplying = progress.phase === 'manual_point';
  const pointApplicationError = progress.phase === 'manual_point_error'
    ? progress.message : '';
  const convergenceHistory = snapshot?.automatic_search?.history || [];
  const roundnessTolerance = finiteNumber(config?.roundness_tolerance_pct) ?? 7;
  const centroidGuidePx = finiteNumber(config?.tolerance_px) ?? 2;
  const progressRoundnessError = roundnessError(progress);
  const referenceRoundness = finiteNumber(progress.reference_roundness_pct);
  const testRoundness = finiteNumber(progress.test_roundness_pct);
  const activePoint = snapshot?.active_point || '';
  const activeActuatorGroup = actuatorGroupForPoint(activePoint);
  const activePairActuators = (snapshot?.actuators || []).filter(
    (actuator) => actuatorGroupForRole(actuator.role, snapshot?.groups || {}) === activeActuatorGroup
  );
  const activePairReady = activeActuatorGroup > 0
    && activePairActuators.length === 2
    && activePairActuators.every((actuator) => actuatorVisualState(actuator) === 'ready');
  const pairInitialization = snapshot?.pair_initialization || {};
  const activeOpticalLabel = activeActuatorGroup
    ? (hasTranslation
      ? (activeActuatorGroup === 1 ? 'Near plane' : 'Far plane')
      : `Diaphragm ${activeActuatorGroup}`)
    : '';
  const controlsDisabled = Boolean(busy)
    || running
    || pointApplying
    || !snapshot?.capabilities?.interlocked_motion;
  const pointControlsDisabled = controlsDisabled || !snapshot?.capabilities?.apply_point;

  useEffect(() => {
    if (!config) return;
    const schedule = Array.isArray(config.step_schedule) && config.step_schedule.length === 3
      ? config.step_schedule : [10, 6, 2];
    if (config.step_coarse === undefined) {
      setConfig({
        ...config,
        step_coarse: schedule[0],
        step_middle: schedule[1],
        step_fine: schedule[2],
      });
    }
  }, [config]);

  if (!snapshot || !config) {
    return (
      <div className="laser-controller-card">
        <h2>{deviceName}</h2>
        <p>{error || 'Loading LaserPointing controller…'}</p>
      </div>
    );
  }

  const updateConfig = (name, value) => setConfig((current) => ({
    ...current,
    [name]: value,
  }));

  const selectedPointName = pointTransition?.name || activePoint;
  const selectedOpticalPoint = numberedPoints.find(
    (point) => point.name === selectedPointName
  ) || (workingPoint?.[0] === selectedPointName
    ? { name: workingPoint[0], settings: workingPoint[1], number: 'working' }
    : null);

  const renderOpticalPointSelector = () => (
    <section className="laser-panel">
      <div className="laser-section-heading">
        <strong>Optical points</strong>
        <span>Apply point presets · shared across modes</span>
      </div>
      {[0, 1].map((planeIndex) => (
        <div className="laser-point-plane" key={planeIndex}>
          <span className="laser-plane-label">
            {hasTranslation
              ? (planeIndex === 0 ? 'Near' : 'Far')
              : `D${planeIndex + 1}`}
          </span>
          <div className="laser-point-buttons">
            {numberedPoints
              .filter((point) => Math.floor((point.number - 1) / 3) === planeIndex)
              .map((point) => {
                const aperture = pointAperture(point.settings);
                return (
                  <button
                    type="button"
                    key={point.name}
                    className={(pointTransition?.name || activePoint) === point.name ? 'selected' : ''}
                    onClick={() => activateOpticalPoint(point)}
                    disabled={pointControlsDisabled}
                    aria-label={`Point ${point.number} ${pointSensitivity(point.name)} ${aperture !== null ? `${aperture}%` : 'preset'}`}
                    title={Object.entries(point.settings).map(([key, value]) => `${key}=${value}`).join(', ')}
                  >
                    <strong>P{point.number}</strong>
                    <small>{aperture !== null ? `${aperture}%` : 'preset'}</small>
                  </button>
                );
              })}
          </div>
        </div>
      ))}
      {workingPoint && (
        <button
          type="button"
          className={`laser-working-button ${(pointTransition?.name || activePoint) === workingPoint[0] ? 'selected' : ''}`}
          onClick={() => activateOpticalPoint({
            name: workingPoint[0], settings: workingPoint[1], number: 'working',
          })}
          disabled={pointControlsDisabled}
        >
          Working / open configuration
        </button>
      )}
      <OpticalPointState
        point={selectedOpticalPoint}
        snapshot={snapshot}
        transition={pointTransition}
      />
    </section>
  );

  const renderActivePairPanel = () => (
    <section className="laser-panel">
      <div className="laser-section-heading">
        <strong>Active Standa pair</strong>
        <span>
          {activeActuatorGroup
            ? (activePairReady
              ? `${activeOpticalLabel} · pair ${activeActuatorGroup} ready`
              : `${activeOpticalLabel} · initialise pair ${activeActuatorGroup}`)
            : 'Select point 1–3 or 4–6 first'}
        </span>
      </div>
      <div className="laser-pair-initialization">
        <button
          type="button"
          onClick={() => execute(
            'initialize_active_pair',
            undefined,
            `Initializing Standa pair ${activeActuatorGroup}`
          )}
          disabled={Boolean(busy)
            || running
            || !activeActuatorGroup
            || !snapshot.capabilities?.initialize_active_pair}
        >
          {activeActuatorGroup
            ? `Initialize Standa pair ${activeActuatorGroup}`
            : 'Initialize active pair'}
        </button>
        <span>
          {activePairReady
            ? `Pair ${activeActuatorGroup} ready`
            : (pairInitialization.message || 'Axes initialize sequentially: X then Y')}
        </span>
      </div>
    </section>
  );

  return (
    <article className="laser-controller-card">
      <header className="laser-controller-header">
        <div>
          <h2>{deviceName.split('/').pop()}</h2>
          <span>{deviceName}</span>
        </div>
        <div className={`laser-search-badge status-${searchStatus.split(':')[0]}`}>
          {searchStatus}
        </div>
      </header>

      {error && <div className="laser-error-banner">{error}</div>}
      {!error && pointApplicationError && (
        <div className="laser-error-banner">{pointApplicationError}</div>
      )}
      {!snapshot.camera?.centroid_valid && (
        <div className="laser-warning-banner">
          Laser centroid is not visible. Automatic search is unavailable; manual optical
          point selection and Standa movement remain available.
        </div>
      )}
      {(!snapshot.capabilities?.automatic_search
        || !snapshot.capabilities?.apply_point
        || !snapshot.capabilities?.manual_point_selection
        || !snapshot.capabilities?.initialize_active_pair
        || !snapshot.capabilities?.interlocked_motion) && (
        <div className="laser-warning-banner">
          This controller is still running the previous DS version. Restart DS_LaserPointing
          during the next safe maintenance window to enable automatic search, point presets,
          manual pair selection, pair initialisation, convergence history, and the mount
          safety interlock.
        </div>
      )}

      <div className="laser-shared-overview">
        {renderOpticalPointSelector()}
        <ComponentStatusPanel snapshot={snapshot} />
      </div>

      <div className="laser-mode-tabs" role="tablist" aria-label="LaserPointing operating mode">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'automatic'}
          className={activeTab === 'automatic' ? 'active' : ''}
          onClick={() => setActiveTab('automatic')}
        >
          Automatic
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'manual'}
          className={activeTab === 'manual' ? 'active' : ''}
          onClick={() => setActiveTab('manual')}
        >
          Manual
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'other'}
          className={activeTab === 'other' ? 'active' : ''}
          onClick={() => setActiveTab('other')}
        >
          Other
        </button>
      </div>

      <div className="laser-controller-grid">
        <CameraPreview
          camera={snapshot.camera?.device}
          state={snapshot.camera?.state}
          enabled={snapshot.camera?.grabbing ?? !['OFF', 'FAULT', 'UNKNOWN'].includes(
            String(snapshot.camera?.state || 'UNKNOWN').toUpperCase()
          )}
          history={convergenceHistory}
          progress={progress}
          tolerance={centroidGuidePx}
          hasTranslation={hasTranslation}
          onRefresh={loadSnapshot}
        />

        {activeTab === 'automatic' && (
          <div className="laser-control-column" role="tabpanel" aria-label="Automatic alignment">
            {renderActivePairPanel()}

            <section className="laser-panel">
              <div className="laser-section-heading">
                <strong>Automatic alignment</strong>
                <span>
                  {busy || (progressRoundnessError !== null
                    ? `${progress.stage || progress.phase || 'Measuring'} · roundness error ${progressRoundnessError.toFixed(2)}%`
                    : (progress.message || progress.phase || 'Ready'))}
                </span>
              </div>
              <div className="laser-search-form">
                <label>
                  Sequence
                  <select value={config.mode} onChange={(event) => updateConfig('mode', event.target.value)}>
                    <option value="sensitive">Points 3 ↔ 6 (sensitive)</option>
                    <option value="medium">Points 2 ↔ 5 (medium)</option>
                    <option value="staged">2 ↔ 5, then 3 ↔ 6</option>
                  </select>
                </label>
                {['coarse', 'middle', 'fine'].map((level) => (
                  <label key={level}>
                    {level[0].toUpperCase() + level.slice(1)} step
                    <input
                      type="number"
                      min="0.1"
                      step="0.1"
                      value={config[`step_${level}`] ?? ''}
                      onChange={(event) => updateConfig(`step_${level}`, Number(event.target.value))}
                    />
                  </label>
                ))}
                <label>
                  Radius
                  <input type="number" min="0.1" value={config.radius} onChange={(event) => updateConfig('radius', Number(event.target.value))} />
                </label>
                <label>
                  Roundness error (%)
                  <input type="number" min="0" max="100" step="0.1" value={roundnessTolerance} onChange={(event) => updateConfig('roundness_tolerance_pct', Number(event.target.value))} />
                </label>
                <label>
                  Evaluations
                  <input type="number" min="1" value={config.max_evaluations} onChange={(event) => updateConfig('max_evaluations', Number(event.target.value))} />
                </label>
                <label>
                  Samples
                  <input type="number" min="1" value={config.samples} onChange={(event) => updateConfig('samples', Number(event.target.value))} />
                </label>
              </div>
              {(referenceRoundness !== null || testRoundness !== null || progressRoundnessError !== null) && (
                <div className="laser-roundness-metrics" aria-label="Current beam roundness metrics">
                  <span>Reference <strong>{referenceRoundness === null ? '—' : `${referenceRoundness.toFixed(2)}%`}</strong></span>
                  <span>Test <strong>{testRoundness === null ? '—' : `${testRoundness.toFixed(2)}%`}</strong></span>
                  <span>Error <strong>{progressRoundnessError === null ? '—' : `${progressRoundnessError.toFixed(2)}%`}</strong></span>
                </div>
              )}
              <div className="laser-search-actions">
                <button type="button" className="start" onClick={startSearch} disabled={Boolean(busy) || running || !snapshot.camera?.centroid_valid || !snapshot.capabilities?.automatic_search}>
                  Start automatic search
                </button>
                <button type="button" className="stop" onClick={() => execute('stop_automatic_search', undefined, 'Stopping')} disabled={Boolean(busy) || !running || !snapshot.capabilities?.automatic_search}>
                  Stop
                </button>
              </div>
            </section>

            <section className="laser-panel">
              <div className="laser-section-heading">
                <strong>Convergence over time</strong>
                <span>Closed-aperture beam-shape error after each Standa correction</span>
              </div>
              <ConvergenceChart
                history={convergenceHistory}
                tolerance={roundnessTolerance}
                hasTranslation={hasTranslation}
              />
            </section>
          </div>
        )}

        {activeTab === 'manual' && (
          <div className="laser-manual-tab" role="tabpanel" aria-label="Manual hardware controls">
          <section className="laser-panel">
            <div className="laser-section-heading">
              <strong>Standa alignment mounts</strong>
              <span>
                {activeActuatorGroup
                  ? `${activeOpticalLabel} · pair ${activeActuatorGroup} selected`
                  : 'Direct manual controls · point selection is optional'}
              </span>
            </div>
            <div className="laser-actuator-list">
              {(snapshot.actuators || []).map((actuator) => {
                const roleGroup = actuatorGroupForRole(actuator.role, snapshot.groups);
                const active = Boolean(activeActuatorGroup) && roleGroup === activeActuatorGroup;
                const lockReason = active
                  ? (activePairReady
                    ? `Standa pair ${activeActuatorGroup} is active`
                    : `Standa pair ${activeActuatorGroup} is not ready`)
                  : `Manual control available · Standa pair ${roleGroup || '?'}`;
                return (
                  <CompactActuator
                    key={actuator.role}
                    actuator={actuator}
                    active={active}
                    lockReason={lockReason}
                    disabled={Boolean(busy)
                      || running
                      || pointApplying
                      || actuatorVisualState(actuator) !== 'ready'
                      || actuator.move_supported === false}
                    onMove={moveActuator}
                  />
                );
              })}
            </div>
          </section>

          {(snapshot.manual_devices || []).map((hardware) => (
            <ManualDevice
              key={hardware.role}
              hardware={hardware}
              disabled={Boolean(busy) || running}
              onMove={moveManualAxis}
            />
          ))}
          </div>
        )}

        {activeTab === 'other' && (
          <div className="laser-diaphragm-tab" role="tabpanel" aria-label="Other optical controls">
            <section className="laser-panel laser-diaphragm-intro">
              <div className="laser-section-heading">
                <strong>Other optical controls</strong>
                <span>Diaphragms, λ/2 plate, and controller-owned flippers</span>
              </div>
              <p>
                Use the configured percentage presets or move each optic directly. These
                controls do not require selecting or initializing a Standa pair.
              </p>
            </section>
            {(snapshot.other_devices || snapshot.diaphragms || []).map((diaphragm) => (
              <DiaphragmControl
                key={diaphragm.role}
                diaphragm={diaphragm}
                disabled={Boolean(busy) || running}
                onMove={moveOtherDevice}
                onStop={stopOtherDevice}
              />
            ))}
            {!(snapshot.other_devices || snapshot.diaphragms || []).length && (
              <section className="laser-panel">
                No diaphragm, λ/2, or flipper devices are configured for this controller.
              </section>
            )}
          </div>
        )}
      </div>
    </article>
  );
};

export default LaserPointingController;
