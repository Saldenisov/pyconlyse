import { startPreviewPolling } from './vd2PreviewPolling';

afterEach(() => jest.restoreAllMocks());

function clock() {
  let now = 0;
  const pending = [];
  jest.spyOn(performance, 'now').mockImplementation(() => now);
  jest.spyOn(window, 'setTimeout').mockImplementation((callback, delay) => {
    pending.push({ callback, delay });
    return pending.length;
  });
  jest.spyOn(window, 'clearTimeout').mockImplementation(() => {});
  return { pending, set: value => { now = value; }, advance: value => { now += value; } };
}

test('late timer wakeups do not accumulate drift beyond the 200 ms cadence', async () => {
  const time = clock();
  const read = jest.fn(async () => { time.advance(35); });
  const stop = startPreviewPolling(read, 200);
  await Promise.resolve();
  expect(time.pending[0].delay).toBe(165);
  time.set(207); // Browser woke seven milliseconds late.
  await time.pending[0].callback();
  expect(time.pending[1].delay).toBe(158); // Next request remains due at 400.
  time.set(400);
  await time.pending[1].callback();
  expect(time.pending[2].delay).toBe(165);
  stop();
  expect(window.clearTimeout).toHaveBeenCalledWith(3);
});

test('Live uses a 190 ms period to leave headroom below the 200 ms camera cycle', async () => {
  const time = clock();
  const stop = startPreviewPolling(async () => { time.advance(40); });
  await Promise.resolve();
  expect(time.pending[0].delay).toBe(150);
  stop();
});

test('slow transfer has one outstanding read and never queues catch-up requests', async () => {
  const time = clock();
  let finish;
  const read = jest.fn(() => new Promise(resolve => { finish = resolve; }));
  const stop = startPreviewPolling(read);
  time.set(450);
  expect(read).toHaveBeenCalledTimes(1);
  expect(time.pending).toHaveLength(0);
  finish();
  await Promise.resolve();
  expect(time.pending).toHaveLength(1);
  expect(time.pending[0].delay).toBe(0);
  const running = time.pending[0].callback();
  expect(read).toHaveBeenCalledTimes(2);
  stop();
  finish();
  await running;
  expect(time.pending).toHaveLength(1);
});

test('a cached frame is retried promptly without shifting the next normal deadline', async () => {
  const time = clock();
  let calls = 0;
  const stop = startPreviewPolling(async () => { calls += 1; return calls === 1; });
  await Promise.resolve();
  expect(time.pending[0].delay).toBe(20);
  time.set(20);
  await time.pending[0].callback();
  expect(time.pending[1].delay).toBe(170);
  stop();
});

test('repeated cached responses cannot create an unbounded fast retry loop', async () => {
  const time = clock();
  const stop = startPreviewPolling(async () => true);
  await Promise.resolve();
  for (const [index, at] of [[0, 20], [1, 60], [2, 120]]) {
    time.set(at);
    await time.pending[index].callback();
  }
  expect(time.pending.map(item => item.delay)).toEqual([20, 40, 60, 70]);
  stop();
});

test.each([false, true])('a busy preview reader only retries early for direct Tango (%s)', async (direct) => {
  const time = clock();
  const stop = startPreviewPolling(async () => 'waiting_for_frame', 140, direct);
  await Promise.resolve();
  expect(time.pending[0].delay).toBe(direct ? 20 : 140);
  stop();
});

test.each([[200, 140], [100, 70]])('direct polling retains frames at a %d ms camera interval', async (interval, period) => {
  const time = clock();
  const frames = [];
  const missedOnce = new Set();
  let now = 0;
  const stop = startPreviewPolling(async () => {
    const stamp = Math.floor(now / interval);
    const transfer = 25 + (stamp % 3) * 5;
    now += transfer;
    time.set(now);
    if (stamp === frames.at(-1)) return true;
    // A second client briefly owns Web's preview lock.
    if (stamp % 5 === 2 && !missedOnce.has(stamp)) {
      missedOnce.add(stamp);
      return 'waiting_for_frame';
    }
    frames.push(stamp);
    return undefined;
  }, period, true);
  await Promise.resolve();
  for (let index = 0; now < interval * 20; index += 1) {
    now += time.pending[index].delay;
    time.set(now);
    await time.pending[index].callback();
  }
  expect(frames.filter(stamp => stamp < 20)).toEqual(Array.from({ length: 20 }, (_, stamp) => stamp));
  stop();
});
