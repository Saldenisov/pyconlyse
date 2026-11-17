import { CARDS, ParameterCard } from '../PumpProbeVD2.API_BASE';
import VD2LiveAverage from './VD2LiveAverage';

const delays = Array.from('abcdefgh', channel => `delay_${channel}`);
const liveFields = {
  camera: ['time_range', 'streak_mode', 'gate_mode', 'mcp_gain', 'streak_shutter',
    'streak_trigger_mode', 'streak_trigger_status', 'live_exposure_time'],
  timing: ['delay_trigger_mode', 'delay_repetition_rate', ...delays],
  spectrograph: ['wavelength_nm', 'grating', 'spectrograph_shutter', 'focus_mirror', 'exit_mirror', 'slit_width_um'],
};

const liveCards = CARDS.map(card => ({
  ...card,
  title: card.tone === 'spectrograph' ? 'Kymera' : card.title,
  fields: card.fields.filter(field => liveFields[card.tone].includes(field.key)).map(field => (
    delays.includes(field.key) ? { ...field, unit: 'µs', step: 0.000005 } : field
  )),
}));

const directEditable = new Set(['time_range', 'wavelength_nm', 'grating', 'streak_shutter', 'spectrograph_shutter']);

export default function VD2LiveSettings({ values, onApply, disabled, live, legacyAverage, directTango, onAverageReadError }) {
  const liveValues = { ...values };
  if (directTango && liveValues.slit_width_um == null) liveValues.slit_width_um = 'Readback unavailable';
  for (const key of delays) {
    const seconds = values[key];
    if (seconds != null && seconds !== '' && Number.isFinite(Number(seconds))) {
      liveValues[key] = Number((Number(seconds) * 1e6).toFixed(6));
    }
  }

  const apply = (key, value) => {
    if (delays.includes(key)) {
      const microseconds = Number(value);
      if (value === '' || !Number.isFinite(microseconds)) return;
      onApply(key, String(microseconds / 1e6));
    } else {
      onApply(key, value);
    }
  };

  return (
    <aside className="vd2-live-settings" aria-label="Live instrument settings">
      {liveCards.map(card => {
        const directFields = card.fields.map(field => directEditable.has(field.key) ? field : {...field, readOnly: true});
        if (card.tone === 'timing') directFields.unshift({key: 'dg_output', label: 'Output', readOnly: true});
        return <ParameterCard key={card.tone} card={directTango ? {...card, fields: directFields} : card} values={liveValues} onApply={apply}
          compact busy={disabled} disabledFields={live ? ['time_range'] : undefined} />
      })}
      {legacyAverage && <VD2LiveAverage disabled={disabled} onReadError={onAverageReadError} />}
    </aside>
  );
}
