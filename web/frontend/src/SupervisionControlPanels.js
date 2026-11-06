import React from 'react';
import { AcquisitionCommand, useAcquisitionPanelName } from './AcquisitionCommands';
import { DISPLAY_RULES, projectDisplay, readBankField } from './elyseLiveProjection';
import PressureReadout from './PressureReadout';
import panels from './elyseControlPanels.json';
import './SupervisionControlPanels.css';

const GRAY = '#88939e';
const rules = (page) => Object.fromEntries(DISPLAY_RULES.filter((r) => r.page === page).map((r) => [r.target_field, r]));
const rowsFor = (page, t) => Object.fromEntries(Object.entries(rules(page)).map(([field, rule]) => [field,
  projectDisplay(rule, t.payload, t.elapsed, t.failure)]));
const unknown = (label) => ({ label, value: null, quality: 'UNQUALIFIED' });
const source = (row) => row.bank ? `${row.bank}[${row.index}] · ${row.quality}` : 'Source télémétrie non établie';

const COMMAND_OPERATIONS = {
  'Marche alimentation HT': 'alimentation_ht.start', 'Reset alimentation HT': 'alimentation_ht.reset',
  'Arrêt alimentation HT': 'alimentation_ht.stop', 'Marche impulsions modulateur': 'modulator_impulse.start',
  'Arrêt impulsions modulateur': 'modulator_impulse.stop',
};
function Command({ children, label }) {
  return <AcquisitionCommand name={`${label || children} · désactivé`} operation={COMMAND_OPERATIONS[label]}
    className="sup-control__command">{children}</AcquisitionCommand>;
}

function Indicator({ page, field, rows, label }) {
  const palette = panels.pages[page].fields[field];
  const row = rows[field] || unknown(label || palette.label);
  const fresh = row.quality === 'FRESH' && typeof row.value === 'boolean';
  const neutral = palette.false_text === palette.true_text ? palette.false_text : row.label;
  return <div className="sup-control__indicator" aria-label={`${row.label} · ${fresh ? String(row.value) : 'inconnu'}`}
    title={source(row)} style={{ backgroundColor: fresh ? row.value ? palette.true_color : palette.false_color : GRAY }}>
    {label || (fresh ? row.value ? palette.true_text : palette.false_text : neutral)}
    {!fresh && <small>INCONNU</small>}</div>;
}

function Reading({ row, decimals = 1, unit, label }) {
  const r = row || unknown(label);
  return <span className={`sup-control__reading${r.quality === 'FRESH' ? '' : ' sup-control__reading--unknown'}`}
    title={source(r)}><output aria-label={label || r.label}>{r.value === null || r.value === undefined
      ? '—' : r.value.toFixed(decimals).replace('.', ',')}</output> <span>{unit ?? r.unit}</span></span>;
}

function Adjuster({ title, unit, row, decimals = 1, range }) {
  return <section className="sup-control__adjuster" aria-label={title}><h4>{title}{range && <small>{range}</small>}</h4>
    <div className="sup-control__adjuster-values"><Command label={`Diminuer rapidement ${title}`}>≪</Command>
      <Command label={`Diminuer ${title}`}>‹</Command>
      <span className="sup-control__setpoint" title="Consigne locale au PC Supervision, non transmise">— {unit}<small>consigne non transmise</small></span>
      <Reading row={row} label={`${title} · lecture`} unit={unit} decimals={decimals} />
      <Command label={`Augmenter ${title}`}>›</Command><Command label={`Augmenter rapidement ${title}`}>≫</Command></div>
  </section>;
}

function Panel({ name, children }) {
  const panelName = useAcquisitionPanelName(name);
  return <section className={`sup-control sup-control--${name.toLowerCase()}`} aria-label={panelName}>
    {children}
  </section>;
}

export function RadioprotectionPanel({ telemetry, compact = false }) {
  const rows = rowsFor('radioprotection', telemetry);
  return <Panel name="Radioprotection">
    {!compact && <h3>Chaîne de sécurité</h3>}<div className="sup-control__security-chain">
      {[[0, 1, 2, 3, 8, 9], [7, 6, 11, 5, 10, 4]].map((fields, col) => <div key={col} role="group"
        aria-label={col === 0 ? 'Portes et rondiers 1 et 2' : 'BACO, arrêts et rondiers 3'}>
        {fields.map((field) => <Indicator key={field} page="radioprotection" field={field} rows={rows} />)}
      </div>)}
    </div>
  </Panel>;
}

export function MachineControlPanel({ telemetry }) {
  // All four cards share the parent's one telemetry snapshot and its freshness
  // checks. Layout does not add command authority, polling or safety decisions.
  return <section className="sup-machine" aria-label="HT, HF, alimentations et radioprotection">
    <div className="sup-machine__grid">
      <section className="sup-machine__block sup-machine__block--ht" aria-label="Commande HT"><h2>HT</h2><HighTensionPanel telemetry={telemetry} /></section>
      <section className="sup-machine__block sup-machine__block--hf" aria-label="Commande HF"><h2>HF</h2><HighFrequencyPanel telemetry={telemetry} /></section>
      <section className="sup-machine__block sup-machine__block--power" aria-label="Alimentations machine"><h2>Alimentations</h2><PowerSuppliesPanel telemetry={telemetry} /></section>
      <section className="sup-machine__block sup-machine__block--radio" aria-label="Sécurité radioprotection"><h2>Radioprotection</h2><RadioprotectionPanel telemetry={telemetry} compact /></section>
    </div>
  </section>;
}

export function HighTensionPanel({ telemetry }) {
  const rows = rowsFor('ht', telemetry);
  const pressureRule = DISPLAY_RULES.find((r) => r.id === 'vide:7');
  const pressure = projectDisplay(pressureRule, telemetry.payload, telemetry.elapsed, telemetry.failure);
  return <Panel name="HT">
    <div className="sup-control__three-columns">
      <section className="sup-control__ht-supply" aria-label="Alimentation HT">
        <div className="sup-control__ht-top"><div className="sup-control__ht-states">
          {[27, 26, 8, 7].map((field) => <Indicator key={field} page="ht" field={field} rows={rows} />)}
        </div><div><h3>Alimentation HT</h3>
          {[[4, 3], [5, 2]].map(([status, value]) => <div className="sup-control__measurement" key={value}>
            <Indicator page="ht" field={status} rows={rows} /><Reading row={rows[value]} /></div>)}
        </div></div>
        <h4>Démarrage alimentation HT</h4><div className="sup-control__commands">
          <Command label="Marche alimentation HT">MARCHE</Command><Command label="Reset alimentation HT">RESET</Command><Command label="Arrêt alimentation HT">ARRET</Command>
        </div>
      </section>
      <section className="sup-control__ht-adjustments" aria-label="Réglages HT et préampli">
        <Adjuster title="Préamplificateur HF" unit="W" decimals={0} range="240 à 400 W" />
        <Adjuster title="Consigne HT" unit="kV" row={rows[17]} range="0 à 20 kV" />
      </section>
      <section className="sup-control__ht-pulses" aria-label="Impulsions modulateur">
        <Indicator page="ht" field={6} rows={rows} />
        <div className="sup-control__pressure"><span>SECTION</span><PressureReadout value={pressure.value} label="Pression SECTION · HT" /></div>
        <h4>Impulsions modulateur</h4><div className="sup-control__commands"><Command label="Marche impulsions modulateur">MARCHE</Command><Command label="Arrêt impulsions modulateur">ARRET</Command></div>
      </section>
    </div>
  </Panel>;
}

export function HighFrequencyPanel({ telemetry }) {
  const rows = rowsFor('hf', telemetry);
  return <Panel name="HF">
    <div className="sup-control__hf-top"><Indicator page="hf" field={25} rows={rows} />
      <div>Niveau HF du CANON : <Reading row={rows[23]} decimals={2} /></div>
      <div>Niveau HF de la SECTION : <Reading row={rows[24]} decimals={2} /></div></div>
    <div className="sup-control__three-columns sup-control__hf-columns">
      <section aria-label="Démarrage atténuateur et déphaseur">
        <div className="sup-control__hf-inputs">{[9, 8, 10, 11].map((field) => <Indicator key={field} page="hf" field={field} rows={rows} />)}</div>
        <h4>Démarrage de l’atténuateur<br />et du déphaseur HF</h4>
        <div className="sup-control__commands"><Command label="Marche atténuateur et déphaseur HF">MARCHE</Command><Command label="Arrêt atténuateur et déphaseur HF">ARRET</Command></div>
      </section>
      <section aria-label="Atténuateur HF"><div className="sup-control__endstops">{[18, 19].map((field) => <Indicator key={field} page="hf" field={field} rows={rows} />)}</div>
        <Adjuster title="Position de l’atténuateur HF" unit="dB" row={rows[0]} decimals={2} />
      </section>
      <section aria-label="Déphaseur HF"><div className="sup-control__endstops">{[21, 20].map((field) => <Indicator key={field} page="hf" field={field} rows={rows} />)}</div>
        <div className="sup-control__manual-phase">Position du déphaseur manuel : <Reading row={rows[22]} unit="°" /></div>
        <Adjuster title="Position du déphaseur HF" unit="°" row={rows[12]} />
      </section>
    </div>
  </Panel>;
}

export function PowerSuppliesPanel({ telemetry }) {
  const stage = readBankField(telemetry.payload, 'EPS', 58, 'boolean', telemetry.elapsed, telemetry.failure);
  const power = powerSupplyDisplay(telemetry);
  return <Panel name="Alimentations">
    <div className="sup-control__power" aria-label="États et commandes alimentations">
      <section><h3>ÉTATS</h3><div className="sup-control__indicator" aria-label={`Alimentations · ${power.code === null ? 'état agrégé inconnu' : power.text.replace('\n', ' · ')}`}
        title={power.source} style={{ backgroundColor: power.color }}>{power.text}</div>
        <div className="sup-control__indicator" aria-label="Alimentations · défaut inconnu" style={{ backgroundColor: GRAY }}>ALIMENTATIONS<small>DÉFAUT NON QUALIFIÉ</small></div>
        <p className="sup-control__software-stage" title={`EPS[58] · ${stage.quality}`}>Étape logicielle ACQ : {stage.quality === 'FRESH' ? stage.value ? 'ON' : 'OFF' : '—'}</p>
      </section>
      <section><h3>COMMANDE</h3><Command label="Marche alimentations aimants">MARCHE</Command>
        <div className="sup-control__commands"><Command label="Zéro volt alimentations aimants">0V</Command><Command label="Run alimentations aimants">Run</Command></div>
        <Command label="Arrêt alimentations aimants">ARRET</Command>
      </section>
    </div>
  </Panel>;
}

export function powerStateCode(rawBits) {
  if (rawBits.length !== 16 || rawBits.some((v) => typeof v !== 'boolean')) return null;
  const inverted = rawBits.map((v) => !v);
  return Number(inverted.every(Boolean)) + 2 * Number(inverted.some(Boolean));
}

export function powerSupplyDisplay(telemetry) {
  const spec = panels.power_state;
  const bits = spec.indices.map((i) => readBankField(telemetry.payload, spec.bank, i, 'boolean', telemetry.elapsed, telemetry.failure));
  const fresh = bits.every((r) => r.quality === 'FRESH');
  const code = fresh ? powerStateCode(bits.map((r) => r.value)) : null;
  return code === null ? { code, text: 'ALIMENTATIONS\nÉTAT AGRÉGÉ INCONNU', color: GRAY, source: 'C3 · source absente, périmée ou erronée' }
    : { code, ...spec.states[code], source: `${spec.bank}[${spec.indices.join(', ')}] · AND(!bits) + 2 × OR(!bits) · état ${code}` };
}
