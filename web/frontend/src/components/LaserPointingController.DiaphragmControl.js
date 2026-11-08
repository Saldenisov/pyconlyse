import { useEffect, useState } from 'react';
import { actuatorVisualState } from "./LaserPointingController.API_BASE";
import { formatOpticalStatusValue } from "./LaserPointingController.API_BASE";

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

export {
  DiaphragmControl,
};
