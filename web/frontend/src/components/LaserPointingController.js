import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import { API_BASE } from "./LaserPointingController.API_BASE";
import { pointNumber } from "./LaserPointingController.API_BASE";
import { actuatorGroupForPoint } from "./LaserPointingController.API_BASE";
import { actuatorGroupForRole } from "./LaserPointingController.API_BASE";
import { actuatorVisualState } from "./LaserPointingController.API_BASE";
import { pointAperture } from "./LaserPointingController.API_BASE";
import { pointSensitivity } from "./LaserPointingController.API_BASE";
import { finiteNumber } from "./LaserPointingController.API_BASE";
import { roundnessError } from "./LaserPointingController.API_BASE";
import { centeringError } from "./LaserPointingController.API_BASE";
import { ComponentStatusPanel } from "./LaserPointingController.API_BASE";
import { OpticalPointState } from "./LaserPointingController.API_BASE";
import { laserSnapshotErrorMessage } from "./LaserPointingController.API_BASE";
import { cameraVisibilityWarning } from "./LaserPointingController.API_BASE";
import { CameraPreview } from "./LaserPointingController.CameraPreview";
import { ConvergenceChart } from "./LaserPointingController.CameraPreview";
import { CompactActuator } from "./LaserPointingController.CameraPreview";
import { ManualDevice } from "./LaserPointingController.CameraPreview";
import { DiaphragmControl } from "./LaserPointingController.DiaphragmControl";

import './LaserPointingController.css';


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
    if (schedule.some((value) => !Number.isFinite(value) || value < 0.1 || value > 50)) {
      setError('Coarse, middle and fine steps must be between 0.1 and 50.');
      return;
    }
    if (!(schedule[0] > schedule[1] && schedule[1] > schedule[2])) {
      setError('Coarse, middle and fine steps must be strictly decreasing.');
      return;
    }
    const boundedInputs = [
      ['Radius', Number(config.radius), 0.1, 100],
      ['Roundness error', Number(config.roundness_tolerance_pct), 0, 100],
      ['Evaluations', Number(config.max_evaluations), 1, 500],
      ['Samples', Number(config.samples), 1, 5],
      ...(config.alignment_objective === 'centering' ? [
        ['Centering tolerance', Number(config.centering_tolerance_px ?? 1), 0, 100],
        ['Repeat measurements', Number(config.measurement_repetitions ?? 3), 3, 5],
      ] : []),
    ];
    const invalidInput = boundedInputs.find(([, value, minimum, maximum]) => (
      !Number.isFinite(value) || value < minimum || value > maximum
    ));
    if (invalidInput) {
      const [label, , minimum, maximum] = invalidInput;
      setError(`${label} must be between ${minimum} and ${maximum}.`);
      return;
    }
    if (!Number.isInteger(Number(config.max_evaluations))
      || !Number.isInteger(Number(config.samples))
      || (config.alignment_objective === 'centering' && !Number.isInteger(Number(config.measurement_repetitions ?? 3)))) {
      setError('Evaluations and samples must be whole numbers.');
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
  const running = [
    'running', 'pausing', 'paused', 'cancelling', 'restoring',
    'cancelling; keeping current',
  ].includes(searchStatus);
  const paused = searchStatus === 'paused' || searchStatus === 'pausing';
  const cancelling = [
    'cancelling', 'restoring', 'cancelling; keeping current',
  ].includes(searchStatus);
  const progress = snapshot?.automatic_search?.progress || {};
  const pointApplying = progress.phase === 'manual_point';
  const pointApplicationError = progress.phase === 'manual_point_error'
    ? progress.message : '';
  const convergenceHistory = snapshot?.automatic_search?.history || [];
  const acceptedReference = snapshot?.automatic_search?.reference || {};
  const pendingReference = snapshot?.automatic_search?.pending_reference || {};
  const hasAcceptedReference = Object.keys(acceptedReference).length > 0;
  const hasPendingReference = Object.keys(pendingReference).length > 0;
  const referenceRevision = snapshot?.automatic_search?.reference_revision || 0;
  const roundnessTolerance = finiteNumber(config?.roundness_tolerance_pct) ?? 7;
  const centeringMode = config?.alignment_objective === 'centering';
  const centeringTolerance = finiteNumber(config?.centering_tolerance_px) ?? 1;
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
    || hasPendingReference
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
          title="DS sequence: set λ/2 working target, apply all Working optics, then lower and verify all shutters"
        >
          Working / open beam
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
      {cameraVisibilityWarning(snapshot.camera) && (
        <div
          className="laser-warning-banner"
          role={snapshot.camera?.ambient_light_high ? 'alert' : undefined}
        >
          {cameraVisibilityWarning(snapshot.camera)}
        </div>
      )}
      {(!snapshot.capabilities?.automatic_search
        || !snapshot.capabilities?.apply_point
        || !snapshot.capabilities?.manual_point_selection
        || !snapshot.capabilities?.initialize_active_pair
        || !snapshot.capabilities?.cancel_search_keep_current
        || !snapshot.capabilities?.save_current_alignment_reference
        || !snapshot.capabilities?.interlocked_motion) && (
        <div className="laser-warning-banner">
          This controller is still running the previous DS version. Restart DS_LaserPointing
          during the next safe maintenance window to enable automatic search, point presets,
          manual pair selection, pair initialisation, convergence history, and the mount
          safety interlock, both cancellation modes, and manual reference saving.
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
          controllerName={snapshot.device}
          state={snapshot.camera?.state}
          enabled={snapshot.camera?.grabbing ?? !['OFF', 'FAULT', 'UNKNOWN'].includes(
            String(snapshot.camera?.state || 'UNKNOWN').toUpperCase()
          )}
          history={convergenceHistory}
          progress={progress}
          tolerance={centroidGuidePx}
          hasTranslation={hasTranslation}
          showAutomaticContours={['running', 'pausing', 'paused'].includes(searchStatus)}
          onRefresh={loadSnapshot}
        />

        {activeTab === 'automatic' && (
          <div className="laser-control-column" role="tabpanel" aria-label="Automatic alignment">
            {renderActivePairPanel()}

            <section className="laser-panel">
              <div className="laser-section-heading">
                <strong>Automatic alignment</strong>
                <span>
                  {busy || (centeringMode
                    ? (centeringError(progress) !== null
                      ? `${progress.stage || progress.phase || 'Measuring'} · center spread ${centeringError(progress).toFixed(2)} px`
                      : (progress.message || progress.phase || 'Ready'))
                    : progressRoundnessError !== null
                    ? `${progress.stage || progress.phase || 'Measuring'} · roundness error ${progressRoundnessError.toFixed(2)}%`
                    : (progress.message || progress.phase || 'Ready'))}
                </span>
              </div>
              <div className="laser-search-form">
                <label>
                  Objective
                  <select value={config.alignment_objective || 'roundness'}
                    disabled={running || snapshot?.automatic_search?.config?.alignment_objective === undefined}
                    onChange={(event) => updateConfig('alignment_objective', event.target.value)}>
                    <option value="roundness">Roundness (legacy)</option>
                    <option value="centering">Centering with repeat confirmation</option>
                  </select>
                </label>
                <label>
                  Sequence
                  <select value={config.mode} onChange={(event) => updateConfig('mode', event.target.value)}>
                    <option value="staged">2 ↔ 5, then 3 ↔ 6</option>
                    <option value="sensitive">Points 3 ↔ 6 (sensitive)</option>
                    <option value="medium">Points 2 ↔ 5 (medium)</option>
                  </select>
                </label>
                {['coarse', 'middle', 'fine'].map((level) => (
                  <label key={level}>
                    {level[0].toUpperCase() + level.slice(1)} step
                    <input
                      type="number"
                      min="0.1"
                      max="50"
                      step="0.1"
                      value={config[`step_${level}`] ?? ''}
                      onChange={(event) => updateConfig(`step_${level}`, Number(event.target.value))}
                    />
                  </label>
                ))}
                <label>
                  Radius
                  <input type="number" min="0.1" max="100" value={config.radius} onChange={(event) => updateConfig('radius', Number(event.target.value))} />
                </label>
                <label>
                  {centeringMode ? 'Centering tolerance (px)' : 'Roundness error (%)'}
                  <input type="number" min="0" max="100" step="0.1" value={centeringMode ? centeringTolerance : roundnessTolerance}
                    onChange={(event) => updateConfig(centeringMode ? 'centering_tolerance_px' : 'roundness_tolerance_pct', Number(event.target.value))} />
                </label>
                {centeringMode && <label>
                  Repeat measurements
                  <input type="number" min="3" max="5" step="1" value={config.measurement_repetitions ?? 3}
                    onChange={(event) => updateConfig('measurement_repetitions', Number(event.target.value))} />
                </label>}
                <label>
                  Evaluations
                  <input type="number" min="1" max="500" value={config.max_evaluations} onChange={(event) => updateConfig('max_evaluations', Number(event.target.value))} />
                </label>
                <label>
                  Samples
                  <input type="number" min="1" max="5" value={config.samples} onChange={(event) => updateConfig('samples', Number(event.target.value))} />
                </label>
              </div>
              {centeringMode && <div className="laser-roundness-metrics" aria-label="Separate centering and ellipticity metrics">
                <span>Center spread <strong>{centeringError(progress)?.toFixed(2) ?? '—'} px</strong></span>
                <span>Ellipticity <strong>{finiteNumber(progress.ellipticity_error_pct)?.toFixed(2) ?? '—'}%</strong> · diagnostic only</span>
                {(progress.verification || []).map((item) => <span key={`${item.group}-${item.point}`}>
                  {item.point}: centers {item.centering_passed ? 'verified' : 'not verified'} · ellipse {item.ellipticity_passed ? 'within tolerance' : 'outside tolerance'}
                </span>)}
              </div>}
              {(referenceRoundness !== null || testRoundness !== null || progressRoundnessError !== null) && (
                <div className="laser-roundness-metrics" aria-label="Current beam roundness metrics">
                  <span>Reference <strong>{referenceRoundness === null ? '—' : `${referenceRoundness.toFixed(2)}%`}</strong></span>
                  <span>Test <strong>{testRoundness === null ? '—' : `${testRoundness.toFixed(2)}%`}</strong></span>
                  <span>Error <strong>{progressRoundnessError === null ? '—' : `${progressRoundnessError.toFixed(2)}%`}</strong></span>
                </div>
              )}
              <div className="laser-search-actions">
                <button type="button" className="start" onClick={startSearch} disabled={Boolean(busy) || running || hasPendingReference || !snapshot.camera?.centroid_valid || !snapshot.capabilities?.automatic_search}>
                  Start automatic search
                </button>
                {!paused ? (
                  <button type="button" onClick={() => execute('pause_automatic_search', undefined, 'Pausing')} disabled={Boolean(busy) || !running || cancelling || !snapshot.capabilities?.pause_search}>
                    Pause
                  </button>
                ) : (
                  <button type="button" className="start" onClick={() => execute('resume_automatic_search', undefined, 'Continuing')} disabled={Boolean(busy) || cancelling || !snapshot.capabilities?.resume_search}>
                    Continue
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => execute(
                    'cancel_automatic_search',
                    undefined,
                    'Stopping and keeping current alignment'
                  )}
                  disabled={Boolean(busy)
                    || (!running && !hasPendingReference)
                    || cancelling
                    || !snapshot.capabilities?.cancel_search_keep_current}
                >
                  {hasPendingReference ? 'Keep current alignment' : 'Cancel — keep current'}
                </button>
                <button type="button" className="stop" onClick={() => execute('stop_automatic_search', undefined, 'Cancelling and restoring initial state')} disabled={Boolean(busy) || (!running && !hasPendingReference) || cancelling || !snapshot.capabilities?.automatic_search}>
                  {hasPendingReference ? 'Discard and restore' : 'Cancel + restore'}
                </button>
              </div>
              {hasPendingReference && (
                <div className="laser-reference-card" role="status" aria-label="Alignment awaiting acceptance">
                  <strong>Alignment finished — operator confirmation required</strong>
                  <span>
                    {pendingReference.converged
                      ? 'Search converged.'
                      : 'Tolerance was not reached; accept only after checking the beam.'}
                  </span>
                  <button
                    type="button"
                    className="start"
                    onClick={() => execute(
                      'accept_alignment_reference',
                      JSON.stringify({ client: 'web' }),
                      'Saving next-day reference'
                    )}
                    disabled={Boolean(busy) || running || !snapshot.capabilities?.accept_alignment_reference}
                  >
                    Accept as next-day reference
                  </button>
                </div>
              )}
              {!running && !hasPendingReference && (
                <div className="laser-reference-card" aria-label="Save current alignment reference">
                  <strong>Current manual alignment</strong>
                  <span>Store the present actuator and optical state as tomorrow's reference.</span>
                  <button
                    type="button"
                    onClick={() => execute(
                      'save_current_alignment_reference',
                      JSON.stringify({ client: 'web' }),
                      'Saving current manual alignment'
                    )}
                    disabled={Boolean(busy) || !snapshot.capabilities?.save_current_alignment_reference}
                  >
                    Save current manual alignment as next-day reference
                  </button>
                </div>
              )}
              <div className="laser-reference-card" aria-label="Accepted alignment reference">
                <strong>Stored reference</strong>
                {hasAcceptedReference ? (
                  <span>
                    Revision {referenceRevision} · {acceptedReference.accepted_at_utc || 'saved'} · {' '}
                    {Object.entries(acceptedReference.actuators || {}).map(
                      ([role, state]) => `${role} ${Number(state.position).toFixed(3)}`
                    ).join(', ')}
                  </span>
                ) : (
                  <span>No accepted reference has been stored yet.</span>
                )}
              </div>
            </section>

            <section className="laser-panel">
              <div className="laser-section-heading">
                <strong>Convergence over time</strong>
                <span>{centeringMode ? 'Center spread in pixels; accepted improvements require repeat confirmation' : 'Closed-aperture beam-shape error after each Standa correction'}</span>
              </div>
              <ConvergenceChart
                history={convergenceHistory}
                tolerance={centeringMode ? centeringTolerance : roundnessTolerance}
                objective={centeringMode ? 'centering' : 'roundness'}
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

export { DeltaVectorChart } from "./LaserPointingController.CameraPreview";

export { ConvergenceChart } from "./LaserPointingController.CameraPreview";

export { CameraPreview } from "./LaserPointingController.CameraPreview";

export { measuredProfileSnapshot } from "./LaserPointingController.API_BASE";

export { alignmentActivityText } from "./LaserPointingController.API_BASE";

export { cameraVisibilityWarning } from "./LaserPointingController.API_BASE";

export { laserSnapshotErrorMessage } from "./LaserPointingController.API_BASE";

export { ComponentStatusPanel } from "./LaserPointingController.API_BASE";

export { formatOpticalStatusValue } from "./LaserPointingController.API_BASE";

export { centeringError } from "./LaserPointingController.API_BASE";

export { roundnessError } from "./LaserPointingController.API_BASE";

export { pointAperture } from "./LaserPointingController.API_BASE";

export { actuatorVisualState } from "./LaserPointingController.API_BASE";

export { actuatorGroupForRole } from "./LaserPointingController.API_BASE";

export { actuatorGroupForPoint } from "./LaserPointingController.API_BASE";

export { pointNumber } from "./LaserPointingController.API_BASE";
