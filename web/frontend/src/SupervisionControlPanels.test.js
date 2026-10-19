import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { RadioprotectionPanel, HighTensionPanel, HighFrequencyPanel, PowerSuppliesPanel, powerStateCode, powerSupplyDisplay } from './SupervisionControlPanels';
import { nextRadioprotectionLog } from './radioprotectionLog';
import palettes from './elyseControlPanels.json';
import { DISPLAY_RULES } from './elyseLiveProjection';

function telemetry() {
  const specs = [['C1NI6071E', 64, 'DBL'], ['C2NI6071E', 64, 'DBL'], ['C3_IN_DIO96', 56, 'Boolean'], ['C4_IN_DIO96', 64, 'Boolean'], ['EPS', 77, 'Boolean'], ['VAM-A', 64, 'DBL']];
  return { elapsed: 0, failure: '', payload: { observed_utc: '2026-10-16T16:00:00Z', stale_after_seconds: 2,
    snapshot: { receiver_session: 'test', publications: Object.fromEntries(specs.map(([name, size, type]) => [name, {
      data: Array(size).fill(type === 'DBL' ? 0 : false), stale: false, age_seconds: 0.1,
      error: { status: false, code: 0 }, lv_type: { type: 'Cluster', name, fields: Array(size).fill({ type }) },
    }])) } } };
}

test('radio chain retains both native columns and all twelve per-field TRUE/FALSE palettes', () => {
  const t = telemetry();
  const view = render(<RadioprotectionPanel telemetry={t} />);
  const columns = [screen.getByRole('group', { name: 'Portes et rondiers 1 et 2' }),
    screen.getByRole('group', { name: 'BACO, arrêts et rondiers 3' })];
  const fields = palettes.pages.radioprotection.fields;
  expect(columns).toHaveLength(2);
  expect(within(columns[0]).getAllByTitle(/C4_IN_DIO96/)).toHaveLength(6);
  expect(within(columns[1]).getAllByTitle(/C4_IN_DIO96/)).toHaveLength(6);
  expect(within(columns[0]).getByText('RONDIER 1')).toBeInTheDocument();
  expect(within(columns[1]).getByLabelText('BACO PA/MOD · false')).toHaveTextContent('BACO');
  const radioRules = DISPLAY_RULES.filter((r) => r.page === 'radioprotection');
  for (const value of [false, true]) {
    t.payload.snapshot.publications.C4_IN_DIO96.data.fill(value);
    view.rerender(<RadioprotectionPanel telemetry={t} />);
    radioRules.forEach((r) => {
      const field = fields[r.target_field];
      expect(screen.getByLabelText(`${r.label} · ${value}`)).toHaveStyle({ backgroundColor: value ? field.true_color : field.false_color });
      expect(screen.getByLabelText(`${r.label} · ${value}`)).toHaveTextContent((value ? field.true_text : field.false_text).replace(/\s+/g, ' '));
    });
  }
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: /Journal|Fiches/ })).not.toBeInTheDocument();
});

test('HT reproduces seven independent C4 states and measured readouts, not local saved setpoints', () => {
  const t = telemetry();
  t.payload.snapshot.publications.C2NI6071E.data[7] = 12.73;
  t.payload.snapshot.publications.C2NI6071E.data[15] = 0.27;
  render(<HighTensionPanel telemetry={t} />);
  expect(screen.getByLabelText('Mesure V HT')).toHaveTextContent('12,7');
  expect(screen.getByLabelText('Mesure I HT')).toHaveTextContent('0,3');
  expect(screen.getByLabelText('HT en marche · false')).toHaveStyle({ backgroundColor: '#00C82D' });
  expect(screen.getByLabelText('Consigne HT · lecture')).toHaveTextContent('12,7');
  expect(screen.getByLabelText('Préamplificateur HF · lecture')).toHaveTextContent('—');
  expect(screen.getAllByText('consigne non transmise')).toHaveLength(2);
  expect(screen.getAllByRole('button')).toHaveLength(13);
  screen.getAllByRole('button').forEach((b) => expect(b).toBeDisabled());
});

test('HF shows both power levels, actual phases and converted attenuation, never guessed green states', () => {
  const t = telemetry();
  t.payload.snapshot.publications.C2NI6071E.data[18] = -0.01;
  t.payload.snapshot.publications.C2NI6071E.data[26] = 0.04;
  t.payload.snapshot.publications.C1NI6071E.data[44] = 3.6;
  t.payload.snapshot.publications.C1NI6071E.data[36] = 3.6;
  render(<HighFrequencyPanel telemetry={t} />);
  expect(screen.getByLabelText('Niveau HF du CANON')).toHaveTextContent('-0,01');
  expect(screen.getByLabelText('Niveau HF de la SECTION')).toHaveTextContent('0,04');
  expect(screen.getByLabelText('Position de l’atténuateur HF · lecture')).not.toHaveTextContent('—');
  expect(screen.getAllByText('NON QUALIFIÉ / INCONNU')).toHaveLength(9);
  expect(screen.getAllByText('consigne non transmise')).toHaveLength(2);
  screen.getAllByRole('button').forEach((b) => expect(b).toBeDisabled());
});

test('Alimentations has only states and disabled commands, no graph, selection or sauvegarde', () => {
  const t = telemetry();
  t.payload.snapshot.publications.EPS.data[58] = true;
  render(<PowerSuppliesPanel telemetry={t} />);
  expect(screen.getAllByRole('button')).toHaveLength(4);
  screen.getAllByRole('button').forEach((b) => expect(b).toBeDisabled());
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  expect(screen.queryByText('SAUVEGARDE')).not.toBeInTheDocument();
  expect(screen.getByText('Étape logicielle ACQ : ON')).toBeInTheDocument();
  expect(screen.getByText('DÉFAUT NON QUALIFIÉ')).toBeInTheDocument();
});

test('power display preserves inverted inputs and all 65536 single-snapshot combinations', () => {
  for (let mask = 0; mask < 65536; mask += 1) {
    const bits = Array.from({ length: 16 }, (_, i) => Boolean(mask & (1 << i)));
    expect(powerStateCode(bits)).toBe(mask === 65535 ? 0 : mask === 0 ? 3 : 2);
  }
  expect(powerStateCode([false])).toBeNull();
  expect(powerStateCode(Array(16).fill(0))).toBeNull();
  const t = telemetry();
  expect(powerSupplyDisplay(t)).toMatchObject({ code: 3, color: '#64FF00', text: 'ALIMENTATIONS\nEN MARCHE' });
  t.payload.snapshot.publications.C3_IN_DIO96.data.fill(true);
  expect(powerSupplyDisplay(t)).toMatchObject({ code: 0, color: '#BCBCBC', text: "ALIMENTATIONS\nA L'ARRET" });
  t.payload.snapshot.publications.C3_IN_DIO96.data[31] = false;
  expect(powerSupplyDisplay(t)).toMatchObject({ code: 2, color: '#EE9A28' });
});

test.each(['stale', 'http', 'read', 'schema'])('no stale/failing green states or live-looking numbers: %s', (reason) => {
  const t = telemetry();
  if (reason === 'stale') t.elapsed = 2;
  if (reason === 'http') t.failure = 'HTTP failed';
  if (reason === 'read') Object.values(t.payload.snapshot.publications).forEach((b) => { b.error.code = 4; });
  if (reason === 'schema') Object.values(t.payload.snapshot.publications).forEach((b) => { b.data.pop(); });
  render(<><RadioprotectionPanel telemetry={t} /><HighTensionPanel telemetry={t} /><HighFrequencyPanel telemetry={t} /><PowerSuppliesPanel telemetry={t} /></>);
  screen.getAllByLabelText(/· inconnu$/).forEach((n) => expect(n).toHaveStyle({ backgroundColor: '#88939e' }));
  expect(screen.getByLabelText('Alimentations · état agrégé inconnu')).toHaveStyle({ backgroundColor: '#88939e' });
  expect(screen.getByLabelText('Alimentations · défaut inconnu')).toHaveStyle({ backgroundColor: '#88939e' });
  const ht = screen.getByRole('region', { name: 'HT · lecture seule' });
  expect(within(ht).getByLabelText('Mesure V HT')).toHaveTextContent('—');
  expect(within(ht).getByLabelText('HT en défaut · inconnu')).not.toHaveTextContent('AUCUN DEFAUT');
  expect(within(ht).getByLabelText('Relais 1 HT · inconnu')).not.toHaveTextContent('FERME');
  expect(screen.getByLabelText('Porte lourde · inconnu')).not.toHaveTextContent('OUVERTE');
});

test('radio log keeps only latest twelve bits, deduplicates and emits observed changes off screen', () => {
  const t = telemetry();
  let next = nextRadioprotectionLog(null, t);
  expect(next.events).toHaveLength(1);
  expect(next.events[0].kind).toBe('snapshot');
  expect(next.state.values).toHaveLength(12);
  expect(nextRadioprotectionLog(next.state, t).events).toEqual([]);
  t.payload.snapshot.publications.C4_IN_DIO96.data[53] = true;
  next = nextRadioprotectionLog(next.state, t);
  expect(next.events).toEqual([expect.objectContaining({ kind: 'observed_change', source: 'C4_IN_DIO96[53]', before: false, after: true })]);
  next = nextRadioprotectionLog(next.state, { ...t, elapsed: 3 });
  expect(next.events[0].quality).toBe('STALE');
  expect(next.state.values).toBeNull();
  expect(nextRadioprotectionLog(next.state, { ...t, elapsed: 4 }).events).toEqual([]);
  next = nextRadioprotectionLog(next.state, t);
  expect(next.events[0].kind).toBe('snapshot'); // no invented edge across outage
  t.payload.snapshot.receiver_session = 'restarted';
  expect(nextRadioprotectionLog(next.state, t).events[0].kind).toBe('snapshot');
});
