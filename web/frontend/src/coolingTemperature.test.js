import { newTemperatureWatch, observeTemperature } from './coolingTemperature';

const reading = (t, value = 21.3, setpoint = 21.1, session = 'owner') => ({
  CANON: { temperature: value, setpoint, key: String(t), session },
  SECTION: { temperature: 28.3, setpoint: 28.2, key: String(t), session },
});
function warm(watch) { for (let t = 0; t <= 30; t += 1) observeTemperature(watch, true, reading(t), t); }

test('normal offset, transient peak and rise below target never warn', () => {
  ['offset', 'spike', 'below'].forEach((scenario) => {
    const w = newTemperatureWatch();
    for (let t = 0; t < 180; t += 1) {
      const v = scenario === 'offset' ? 22.5 : scenario === 'spike' ? t === 60 ? 22.5 : 21.3 : 20 + Math.min(t, 60) / 60;
      expect(observeTemperature(w, true, reading(t, v), t).warnings).toEqual([]);
    }
  });
});

test('growth above unchanged target must persist, then fresh recovery must persist', () => {
  const w = newTemperatureWatch(); warm(w);
  for (let t = 31; t < 46; t += 1) expect(observeTemperature(w, true, reading(t, 22.5), t).warnings).toEqual([]);
  expect(observeTemperature(w, true, reading(46, 22.5), 46).warnings[0].circuit).toBe('CANON');
  expect(observeTemperature(w, null, {}, 47).warnings[0].quality).toBe('UNKNOWN');
  for (let t = 48; t < 78; t += 1) expect(observeTemperature(w, true, reading(t), t).warnings).toHaveLength(1);
  expect(observeTemperature(w, true, reading(78), 78).warnings).toEqual([]);
});

test('gap interrupts pending interval and scope OFF clears it', () => {
  const w = newTemperatureWatch(); warm(w);
  observeTemperature(w, true, reading(31, 22.5), 31);
  expect(observeTemperature(w, true, reading(50, 22.5), 50).warnings).toEqual([]);
  for (let t = 51; t <= 65; t += 1) observeTemperature(w, true, reading(t, 22.5), t);
  expect(observeTemperature(w, true, reading(66, 22.5), 66).warnings).toHaveLength(1);
  expect(observeTemperature(w, false, {}, 67).warnings).toEqual([]);
});

test('intentional setpoint adjustment or new source resets comparison epoch', () => {
  ['setpoint', 'source'].forEach((mode) => {
    const w = newTemperatureWatch(); warm(w);
    for (let t = 31; t < 70; t += 1) {
      const r = reading(t, 22.5, mode === 'setpoint' ? 22.3 : 21.1, mode === 'source' ? 'new' : 'owner');
      expect(observeTemperature(w, true, r, t).warnings).toEqual([]);
    }
  });
});
