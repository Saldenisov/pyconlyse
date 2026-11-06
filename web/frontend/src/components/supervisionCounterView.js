export const COUNTER_STALE_SECONDS = 2;
const SESSION = /^[0-9a-f]{32}$/;
const SOURCES = { PYTHON_NATIVE: 'last_successful_counter_command_memory',
  LABVIEW_BRIDGE: 'observed_labview_control_memory' };
const finite = (value) => typeof value === 'number' && Number.isFinite(value);

export function decodeSupervisionCounter(payload) {
  if (payload?.schema_version !== 1 || payload.owner !== 'supervision'
    || typeof payload.available !== 'boolean' || payload.read_only !== true
    || payload.hardware_acknowledged !== false) {
    throw new Error('Contrat synchronisation SuperVision incompatible.');
  }
  const age = payload.age_seconds;
  if (!payload.available) {
    if (payload.values !== null) throw new Error('Valeurs présentes sans observation actuelle.');
    return { state: finite(age) && age >= 2 ? 'STALE' : 'UNAVAILABLE', values: null,
      age: finite(age) && age >= 0 ? age : null, payload };
  }
  if (payload.stale !== false || !finite(age) || age < 0
    || !SESSION.test(payload.session_id) || !Number.isSafeInteger(payload.sequence) || payload.sequence < 1
    || payload.physical_measurements_verified !== false
    || payload.source !== SOURCES[payload.source_mode] || !Object.hasOwn(SOURCES, payload.source_mode)
    || !Array.isArray(payload.values) || payload.values.length !== 16 || !payload.values.every(finite)
    || !finite(payload.selector) || typeof payload.pending_selector !== 'boolean'
    || (!payload.pending_selector && payload.selector !== -1)) {
    throw new Error('Observation des16 paramètres SuperVision invalide.');
  }
  return { state: age < 2 ? 'CURRENT' : 'STALE', values: payload.values.slice(), age, payload };
}
