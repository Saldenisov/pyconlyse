import { createPreviewFreshnessClock } from './vd2PreviewFreshness';

const received_at = '2026-11-04T12:00:00.200Z';
const serverDate = 'Wed, 04 Nov 2026 12:00:00 GMT';

test.each([-3600000, 3600000])('browser wall-clock offset %s ms cannot make a fresh server frame stale', offset => {
  jest.useFakeTimers();
  try {
    jest.setSystemTime(Date.parse(received_at) + offset);
    const clock = createPreviewFreshnessClock();
    clock.observe({ received_at }, { serverDate, startedAt: 100, receivedAt: 200 });
    expect(clock.status(200)).toMatchObject({ fresh: true, ageMs: 900 });
    jest.setSystemTime(Date.now() + 86400000);
    expect(clock.status(300)).toMatchObject({ fresh: true, ageMs: 1000 });
  } finally { jest.useRealTimers(); }
});

test('duplicate HTTP Date headers are parsed and cached responses never reset frame age', () => {
  const clock = createPreviewFreshnessClock();
  clock.observe({ received_at }, { serverDate: `${serverDate}, ${serverDate}`, startedAt: 100, receivedAt: 200 });
  expect(clock.status(200).fresh).toBe(true);
  clock.observe({ received_at }, { serverDate, startedAt: 900, receivedAt: 1000 });
  expect(clock.status(1000)).toMatchObject({ fresh: false, ageMs: 1700 });
});

test('delayed frames, unavailable server time and future source timestamps remain unverified', () => {
  const clock = createPreviewFreshnessClock();
  clock.observe({ received_at }, { serverDate, startedAt: 100, receivedAt: 2000 });
  expect(clock.status(2000).fresh).toBe(false);
  clock.observe({ received_at: 'invalid' }, { startedAt: 2100, receivedAt: 2200 });
  expect(clock.status(2200)).toMatchObject({ fresh: false, ageMs: null });
  clock.observe({ received_at: '2026-11-04T12:00:05Z' }, { serverDate, startedAt: 2300, receivedAt: 2400 });
  expect(clock.status(2400).fresh).toBe(false);
});

test('a failed read stays visible until a different, verified frame arrives', () => {
  const clock = createPreviewFreshnessClock();
  clock.observe({ received_at }, { serverDate, startedAt: 100, receivedAt: 200 });
  clock.invalidate('Network read failed');
  clock.observe({ received_at }, { serverDate, startedAt: 250, receivedAt: 300 });
  expect(clock.status(300)).toMatchObject({ fresh: false, reason: 'Network read failed' });
  clock.observe({ received_at: '2026-11-04T12:00:00.500Z' }, { serverDate, startedAt: 310, receivedAt: 400 });
  expect(clock.status(400)).toMatchObject({ fresh: true, reason: '' });
});
