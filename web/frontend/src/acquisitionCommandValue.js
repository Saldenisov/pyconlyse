// Named values only. Limits describe encoding, not qualified operating ranges.
export const MAX_SYNC_US = 2147483647 / 20;
export const syncTicks = (value) => {
  const scaled = value * 20;
  const floor = Math.floor(scaled);
  return scaled - floor === 0.5 ? floor + (floor % 2) : Math.round(scaled);
};
export const validSyncValue = (value) => value !== null && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).sort().join(',') === 'counter,delay_us,width_us'
  && Number.isInteger(value.counter) && value.counter >= 0 && value.counter < 8
  && ['delay_us', 'width_us'].every((key) => typeof value[key] === 'number' && Number.isFinite(value[key])
    && value[key] > 0 && value[key] <= MAX_SYNC_US && syncTicks(value[key]) > 0);
export const validCommandValue = (operation, value) => operation === 'ht_voltage.set'
  ? typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 20
  : operation === 'counter_timing.set' ? validSyncValue(value) : value === null;
export const sameCommandValue = (operation, left, right) => operation === 'counter_timing.set'
  ? validSyncValue(left) && validSyncValue(right) && ['counter', 'delay_us', 'width_us'].every((key) => left[key] === right[key])
  : left === right;
export const describeCommandValue = (operation, value) => operation === 'ht_voltage.set' ? `${value} kV`
  : operation === 'counter_timing.set' && validSyncValue(value)
    ? `C10/ctr${value.counter} : délai ${value.delay_us} µs ; largeur ${value.width_us} µs` : '';
