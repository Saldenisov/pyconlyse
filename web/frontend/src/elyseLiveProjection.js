import displayMap from './elyseLiveDisplayMap.json';

export const DISPLAY_RULES = displayMap.rules;
const SCHEMAS = {
  C1NI6071E: [64, 'C1NI6071E'], C2NI6071E: [64, 'C2NI6071E'],
  C3_IN_DIO96: [56, 'C3_IN_DIO96'], C4_IN_DIO96: [64, 'C4_IN_DIO96'],
  C5_IN_DIO96: [56, 'C5_IN_DIO96'], EPS: [77, 'EPS'], 'VAM-A': [64, 'VAM-A'],
  C1011NI6602: [33, 'C10-11 NI6602'],
  C6NI6703: [10, 'C6NI6703'], C7NI6703: [10, 'C7NI6703'], C8NI6703: [10, 'C8NI6703'],
};

// No commands, cached authority, driver, PSP, or telemetry history here.
export function readBankField(payload, bank, index, kind, elapsed = 0, failure = '') {
  const record = payload?.snapshot?.publications?.[bank];
  if (failure) return { quality: 'UNAVAILABLE', value: null };
  // Receiver failure invalidates every retained bank. A different bank's read
  // error or absence does not invalidate an independently fresh field here.
  if ((payload?.server_state !== undefined && payload.server_state !== 'ON')
      || ['RECEIVER_NOT_READY', 'UNAVAILABLE'].includes(payload?.quality)
      || !Number.isFinite(elapsed) || elapsed < 0) {
    return { quality: 'UNAVAILABLE', value: null };
  }
  if (!record) return { quality: 'MISSING', value: null };
  const age = Number.isFinite(record.age_seconds) && record.age_seconds >= 0
    ? record.age_seconds + elapsed : null;
  const limit = Math.min(2, payload?.stale_after_seconds || 2);
  if (record.stale !== false || age === null || age >= limit) return { quality: 'STALE', value: null, age };
  if (record.error?.status !== false || record.error?.code !== 0) return { quality: 'READ_ERROR', value: null, age };
  let type = record.lv_type;
  if (type?.type === 'LvVariant') type = type.contained_type;
  const schema = SCHEMAS[bank];
  const expectedType = kind === 'boolean' ? 'Boolean' : 'DBL';
  if (!schema || type?.type !== 'Cluster' || type.name !== schema[1]
      || !Array.isArray(record.data) || record.data.length !== schema[0]
      || type.fields?.length !== schema[0] || type.fields[index]?.type !== expectedType) {
    return { quality: 'SCHEMA_ERROR', value: null, age };
  }
  const value = record.data[index];
  if (kind === 'boolean' ? typeof value !== 'boolean' : typeof value !== 'number' || !Number.isFinite(value)) {
    return { quality: 'VALUE_ERROR', value: null, age };
  }
  return { quality: 'FRESH', value, age };
}

export function projectDisplay(rule, payload, elapsed = 0, failure = '') {
  const result = readBankField(payload, rule.bank, rule.index, rule.kind, elapsed, failure);
  if (result.quality !== 'FRESH' || rule.kind === 'boolean') return { ...rule, ...result };
  const x = result.value;
  let value;
  if (rule.transform === 'offset_gain') value = (x - rule.offset) * rule.scale;
  else if (rule.transform === 'phase_polynomial') value = 1.1309 * x ** 3 - 5.746 * x ** 2 - 40.368 * x + 102.28;
  else if (rule.transform === 'attenuator_formula') {
    // Formula Node log() means log10; do not replace native 3.1416 with Math.PI.
    const cosine = Math.cos((2 * 3.1416 / 360) * (1.2087 * x ** 3 - 6.5232 * x ** 2 - 15.097 * x + 86.932));
    value = cosine > 0 ? -20 * Math.log10(cosine) : NaN;
  }
  else if (rule.transform === 'identity') value = x * (rule.scale ?? 1);
  else return { ...rule, quality: 'UNQUALIFIED', value: null };
  return { ...rule, ...result, value: Number.isFinite(value) ? value : null,
    quality: Number.isFinite(value) ? 'FRESH' : 'VALUE_ERROR' };
}

export function formatDisplay(value, unit) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE';
  if (unit === 'mbar') return value.toExponential(2).replace('.', ',');
  return value.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export const ACQ_TIMING = ['NI6071E', 'Fréquence ELYSE · paramètre', 'WCM', 'Modulateur',
  'HF', 'Faraday', 'Oscilloscope', 'Synchro 50 Hz / 20 MHz'].flatMap((label, index) =>
  ['Délais', 'Largeur'].map((kind, offset) => ({ id: `synchro:${index * 2 + offset}`,
    page: 'synchro', label: `${kind} ${label}`, bank: 'C1011NI6602', index: index * 2 + offset,
    kind: 'number', unit: 'µs', transform: 'identity', role: 'configured',
    evidence: 'Ordre des 16 champs C10 de la banque ACQ ; pas mesure du signal physique' })));
