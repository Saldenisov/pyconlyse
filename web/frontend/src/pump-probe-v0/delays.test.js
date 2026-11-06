import { DEFAULT_SETTINGS, parseDelayPointsText, parseSamplePositionsText, settingsToApi } from './shared';

describe('V0 delay import', () => {
  test('preserves nonuniform order and repeats', () => {
    expect(parseDelayPointsText('9\n2\n2\n-1')).toEqual([9, 2, 2, -1]);
  });

  test('reads full scientific and decimal tokens', () => {
    expect(parseDelayPointsText('1e3\n-1E-3\n+.5\n5.\n,25\n-1,5e2'))
      .toEqual([1000, -0.001, 0.5, 5, 0.25, -150]);
  });

  test('reads first column of a numeric whitespace table', () => {
    expect(parseDelayPointsText('0\t100\n2 200\n9\t300')).toEqual([0, 2, 9]);
  });

  test('accepts blank lines, BOM, comments and CR line endings', () => {
    expect(parseDelayPointsText('\uFEFF# delays in ps\r\n0\r\n\r\n2\r9'))
      .toEqual([0, 2, 9]);
  });

  test.each(['oops', '1e', '1e+', '1e999', 'NaN', 'Infinity', '3 ps', '0,2,9', '2x3'])(
    'rejects entire import for invalid middle row %s', (row) => {
    expect(() => parseDelayPointsText(`0\n${row}\n9`)).toThrow(/line 2/);
    },
  );

  test.each(['', '0', '# comment\n0'])('rejects too few rows', (text) => {
    expect(() => parseDelayPointsText(text)).toThrow('2..400');
  });

  test('accepts 400 rows and rejects 401 instead of truncating', () => {
    const rows = Array.from({ length: 400 }, (_value, index) => `${index}`);
    expect(parseDelayPointsText(rows.join('\n'))).toHaveLength(400);
    expect(() => parseDelayPointsText([...rows, '400'].join('\n'))).toThrow('2..400');
  });

  test('rejects overflow in derived spacing or span before UI settings are set', () => {
    expect(() => parseDelayPointsText('-1e308\n1e308')).toThrow('spacing and span');
    expect(() => parseDelayPointsText('-1e308\n0\n1e308')).toThrow('spacing and span');
  });

  test('rejects preview and delay-offset overflow before UI settings are set', () => {
    expect(() => parseDelayPointsText('-1e6\n-999999')).toThrow('supported numeric range');
    expect(() => parseDelayPointsText('0\n1e308', 1e308)).toThrow('supported numeric range');
  });

  test.each([NaN, Infinity, null, true, '', '0x10'])('rejects invalid real zero %s', (zero) => {
    expect(() => parseDelayPointsText('0\n2', zero)).toThrow('Real zero');
  });

  test('serializes imported axis together with historical scalar fields', () => {
    const points = parseDelayPointsText('0\n2\n9');
    const settings = { ...DEFAULT_SETTINGS, delayPointsPs: points,
      pointCount: points.length, scanStartPs: points[0], delayStepPs: points[1] - points[0] };
    expect(settingsToApi(settings)).toEqual({
      point_count: 3, scan_start_ps: 0, delay_step_ps: 2, scan_span_ps: 9,
      pulses_per_point: 10, real_zero_ps: 465, delay_points_ps: [0, 2, 9],
    });
  });

  test('sample-marker editing retains empty/single/partial-input behavior', () => {
    expect(parseSamplePositionsText('')).toEqual([]);
    expect(parseSamplePositionsText('1')).toEqual([1]);
    expect(parseSamplePositionsText('1\n-\n2,5')).toEqual([1, 2.5]);
  });
});
