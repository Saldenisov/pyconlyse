import { CIRCULATION_CONFIRMATION, validCommandValue, sameCommandValue } from './acquisitionCommandValue';

const value = () => ({ incident_ids: ['1'.repeat(32), '2'.repeat(32)] });

test('water confirmation targets exact currently displayed UUID episodes', () => {
  expect(validCommandValue(CIRCULATION_CONFIRMATION, value())).toBe(true);
  expect(sameCommandValue(CIRCULATION_CONFIRMATION, value(), value())).toBe(true);
  expect(sameCommandValue(CIRCULATION_CONFIRMATION, value(), { incident_ids: ['1'.repeat(32), '3'.repeat(32)] })).toBe(false);
});

test.each([null, {}, { incident_ids: [] }, { incident_ids: ['1'.repeat(32), '1'.repeat(32)] },
  { incident_ids: ['*'] }, { incident_ids: ['A'.repeat(32)] }, { incident_ids: ['1'.repeat(32)], future: true },
  { incident_ids: ['1'.repeat(32), '2'.repeat(32), '3'.repeat(32)] }])('blanket, malformed or future-episode acknowledgement fails closed: %p', (candidate) => {
  expect(validCommandValue(CIRCULATION_CONFIRMATION, candidate)).toBe(false);
});
