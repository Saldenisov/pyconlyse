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

export const centeringError = (observation = {}) => finiteNumber(observation.centering_error_px);

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

const CAMERA_ADVANCED_PARAMETERS = CAMERA_NUMERIC_PARAMETERS.filter(
  ({ name }) => name !== 'center_gravity_threshold'
);

export const laserSnapshotErrorMessage = (error) => {
  const message = String(error?.message || error || 'Snapshot failed');
  if (/API_CommandTimedOut|not able to acquire serialization/i.test(message)) {
    return 'LaserPointing controller is busy; retrying automatically…';
  }
  return message;
};

export const cameraVisibilityWarning = (camera = {}) => {
  if (camera.ambient_light_high) {
    const rawName = String(camera.device || 'Camera').split('/').pop();
    const cameraName = rawName.replace(/_V0$/i, '').replace(/^Cam(\d+)$/i, 'Camera $1');
    const background = finiteNumber(camera.beam_background);
    const brightFraction = finiteNumber(camera.beam_foreground_fraction);
    const measurement = background !== null && brightFraction !== null
      ? ` Background is ${background.toFixed(0)}/255 and ${(100 * brightFraction).toFixed(0)}% of the image is bright.`
      : '';
    return `${cameraName} cannot be used for alignment: external room light is blocking beam detection.${measurement} Switch off the room light or shield ${cameraName}. Automatic alignment is blocked until a distinct beam is visible.`;
  }
  if (!camera.centroid_valid) {
    const diagnosis = camera.beam_visibility_message || 'Laser centroid is not visible.';
    return `${diagnosis} Automatic search is unavailable; manual optical point selection and Standa movement remain available.`;
  }
  return '';
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
  if (phase === 'confirming_centering') return {
    title: 'Confirming centering with independent repeats',
    detail: 'Rechecking reference and candidate after return; ellipticity is separate',
  };
  if (phase === 'centering_confirmed' || phase === 'centering_probe_rejected') return {
    title: phase === 'centering_confirmed' ? 'Centering confirmed' : 'Unconfirmed improvement rejected',
    detail: `Center spread ${centeringError(progress)?.toFixed(2) ?? '—'} px · ellipticity ${finiteNumber(progress.ellipticity_error_pct)?.toFixed(2) ?? '—'}% (diagnostic)`,
  };
  if (phase === 'finished' && progress.alignment_objective === 'centering') return {
    title: 'Centering verified for selected points',
    detail: progress.ellipticity_passed === false
      ? 'Repeated centering checks passed; ellipticity remains outside its separate tolerance'
      : 'Repeated centering checks passed; shape is reported separately',
  };
  if (phase === 'starting') {
    return { title: 'Preparing automatic alignment', detail: 'Checking camera and optical sequence' };
  }
  if (phase === 'baseline_captured') {
    return {
      title: 'Initial alignment captured',
      detail: progress.message || 'Pre-search actuator and optical state is ready for restore',
    };
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
  if (phase === 'cycling_aperture') {
    const cycle = progress.aperture_cycle ? `Cycle ${progress.aperture_cycle}` : '';
    return {
      title: `Cycling ${progress.aperture_role || 'aperture'}`,
      detail: progress.message || cycle,
    };
  }
  if (phase === 'aperture_cycle_measured') {
    const error = roundnessError(progress);
    return {
      title: 'Aperture response measured',
      detail: progress.message || (error === null ? 'Evaluating drift and roundness' : `Roundness error ${error.toFixed(2)}%`),
    };
  }
  if (phase === 'probe_rejected') {
    return { title: 'Probe rejected — beam disappeared', detail: progress.message || 'Returning to the last visible position' };
  }
  if (phase === 'restoring_last_visible_position') {
    return { title: 'Restoring last visible position', detail: progress.message || 'Rejected actuator move is being reversed' };
  }
  if (phase === 'retaining_last_measured_good_position') {
    return { title: 'Keeping latest measured-good alignment', detail: progress.message || 'Cancellation will not restore the pre-search state' };
  }
  if (phase === 'stopped_no_improvement') {
    return { title: 'Stopped after no roundness improvement', detail: progress.message || 'Latest measured-good alignment is retained' };
  }
  if (phase === 'cancelling_keep_current') {
    return { title: 'Stopping — keeping current alignment', detail: progress.message || 'Waiting for the current hardware operation to finish' };
  }
  if (phase === 'cancelled_keep_current') {
    return { title: 'Stopped — current alignment kept', detail: progress.message || 'No pre-search restore was requested' };
  }
  if (phase === 'restoring_initial_state') {
    return { title: 'Restoring pre-search alignment', detail: progress.message || progress.restoring_role || 'Restoring actuators and optics' };
  }
  if (phase === 'restored_initial_state') {
    return { title: 'Pre-search alignment restored', detail: progress.message || 'Automatic alignment was discarded' };
  }
  if (phase === 'restore_failed') {
    return { title: 'Restore failed', detail: progress.message || 'Check hardware state before moving again' };
  }
  if (phase === 'saving_manual_reference') {
    return { title: 'Saving current manual alignment', detail: progress.message || 'Creating the next-day reference' };
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

export {
  API_BASE, pointSensitivity, formatOpticalValue, finiteNumber, stateName,
  componentVisualState, OpticalPointState, CAMERA_NUMERIC_PARAMETERS,
  CAMERA_PARAMETER_NAMES, CAMERA_ADVANCED_PARAMETERS, PROFILE_COLORS, signedMotorDelta,
  BeamProfileSummary, drawBeamOverlays,
};
