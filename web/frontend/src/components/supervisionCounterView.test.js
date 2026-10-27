import { decodeSupervisionCounter } from './supervisionCounterView';

const current = () => ({ schema_version: 1, owner: 'supervision', available: true,
  stale: false, values: Array(16).fill(1), age_seconds: .1, session_id: 'a'.repeat(32),
  sequence: 1, read_only: true, hardware_acknowledged: false, physical_measurements_verified: false,
  source_mode: 'PYTHON_NATIVE', source: 'last_successful_counter_command_memory',
  selector: -1, pending_selector: false });

test('requires exactly16 finite owner values and never uses legacy C1011', () => {
  expect(decodeSupervisionCounter(current()).values).toHaveLength(16);
  for (const patch of [{ owner: 'acquisition' }, { values: Array(15).fill(1) },
    { values: Array(16).fill(NaN) }, { values: Array(16).fill(true) },
    { hardware_acknowledged: true }, { source: 'observed_labview_control_memory' }]) {
    expect(() => decodeSupervisionCounter({ ...current(), ...patch })).toThrow();
  }
  expect(() => decodeSupervisionCounter({ schema_version: 1, snapshot: { publications: { C1011NI6602: { data: Array(33).fill(1) } } } })).toThrow();
});

test('pending selector remains observed memory and does not imply acknowledgement', () => {
  expect(decodeSupervisionCounter({ ...current(), selector: 3, pending_selector: true }).state).toBe('CURRENT');
  expect(() => decodeSupervisionCounter({ ...current(), selector: 3 })).toThrow();
});

test('unavailable observations require absent values and old current observations expire', () => {
  expect(decodeSupervisionCounter({ ...current(), age_seconds: 2 }).state).toBe('STALE');
  expect(decodeSupervisionCounter({ ...current(), available: false, values: null }).state).toBe('UNAVAILABLE');
  expect(() => decodeSupervisionCounter({ ...current(), available: false })).toThrow();
});
