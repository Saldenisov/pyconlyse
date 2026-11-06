import React from 'react';
import { AcquisitionCommand, useAcquisitionPanelName } from './AcquisitionCommands';
import { DISPLAY_RULES, projectDisplay, readBankField } from './elyseLiveProjection';
import { temperaturePaths, isolatedTrendSamples, TREND_WINDOW_MINUTES } from './fluidesTrend';
import panel from './elyseFluidesPanel.json';
import './FluidesPanel.css';

const RULES = Object.fromEntries(DISPLAY_RULES.filter((r) => r.page === 'fluides').map((r) => [r.target_field, r]));
const GRAY = '#88939e';
const format = (value) => Number.isFinite(value) ? value.toFixed(1).replace('.', ',') : '—';
// Reuse one formatter for thousands of SVG point labels. Constructing an Intl
// formatter for every point on every live update can starve the polling timers.
const temperatureClock = new Intl.DateTimeFormat('fr-FR', {
  timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit', second: '2-digit',
});
const clock = (time) => {
  const date = new Date(time);
  return Number.isFinite(date.getTime()) ? temperatureClock.format(date) : 'heure inconnue';
};

export function fluidesValve(name, telemetry) {
  const spec = panel.valves[name];
  const bits = spec.indices.map((i) => readBankField(telemetry.payload, spec.bank, i, 'boolean', telemetry.elapsed, telemetry.failure));
  const fresh = bits.every((b) => b.quality === 'FRESH');
  const state = fresh ? Number(bits[0].value) + 2 * Number(bits[1].value) : null;
  return { text: fresh ? spec.states[state].text : `VANNE ${name}\nINCONNUE`,
    color: fresh ? spec.states[state].color : GRAY,
    source: `${spec.bank}[${spec.indices.join(', ')}] · ${fresh ? `état ${state}` : bits.find((b) => b.quality !== 'FRESH').quality}` };
}

function Command({ name, children, operation }) {
  return <AcquisitionCommand name={name} operation={operation} className="fluides-panel__command">{children}</AcquisitionCommand>;
}

function Indicator({ field, rows }) {
  const row = rows[field];
  const style = panel.fields[field];
  const fresh = row?.quality === 'FRESH';
  const text = fresh ? row.value ? style.true_text : style.false_text : `${style.label}\nINCONNU`;
  return <div className="fluides-panel__indicator"
    style={{ backgroundColor: fresh ? row.value ? style.true_color : style.false_color : GRAY }}
    aria-label={`${style.label} · ${fresh ? String(row.value) : 'inconnu'}`}
    title={row ? `${row.bank}[${row.index}] = ${row.value} · ${row.quality}` : 'Source live non établie'}>{text}</div>;
}

function Valve({ name, telemetry }) {
  const valve = fluidesValve(name, telemetry);
  return <div className="fluides-panel__indicator" style={{ backgroundColor: valve.color }}
    title={valve.source} aria-label={valve.text.replace('\n', ' · ')}>{valve.text}</div>;
}

function Temperature({ name, field, rows, telemetry }) {
  const row = rows[field];
  const index = name === 'CANON' ? 1 : 2;
  const setpoint = readBankField(telemetry.payload, 'C8NI6703', index, 'number', telemetry.elapsed, telemetry.failure);
  return <div className="fluides-panel__temperature">
    <span className="fluides-panel__temperature-label">T° {name}</span>
    <div><Command name={`Diminuer consigne ${name} · désactivé`}>◀</Command>
      <Command name={`Augmenter consigne ${name} · désactivé`}>▶</Command></div>
    <span className="fluides-panel__setpoint" title={`C8NI6703[${index}] · ${setpoint.quality} · Consigne transmise à Acquisition, pas température mesurée`}>
      <small>Consigne</small><output aria-label={`Consigne ${name}`}>{format(setpoint.value)}</output> °C</span>
    <span className="fluides-panel__reading" title={`${row.bank}[${row.index}] · ${row.quality}`}>
      <small>Lecture</small><output aria-label={`Température ${name} · lecture`}>{format(row.value)}</output> °C</span>
  </div>;
}

export const FluidesTemperatureChart = React.memo(function FluidesTemperatureChart({ trend, windowMinutes = TREND_WINDOW_MINUTES, onWindowChange }) {
  const samples = trend.samples;
  const values = samples.flatMap((s) => [s.canon, s.section]).filter(Number.isFinite);
  const end = samples[samples.length - 1]?.time;
  const span = Math.max(60000, end - samples[0]?.time || 0);
  const start = end - span;
  const min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max(0.2, (max - min) * 0.15);
  const low = Math.floor((min - pad) * 10) / 10;
  const high = Math.ceil((max + pad) * 10) / 10;
  const x = (t) => 52 + (t - start) / span * 268;
  const y = (v) => 22 + (high - v) / (high - low) * 268;
  return <section className="fluides-trend" aria-label="Températures CANON et SECTION">
    <div className="fluides-trend__header">
      <label>Fenêtre<select aria-label="Durée historique Fluides" value={windowMinutes} disabled={!onWindowChange}
        onChange={(event) => onWindowChange?.(Number(event.target.value))}>
        {[5, 15, 30, 60, 120].map((minutes) => <option key={minutes} value={minutes}>{minutes} min</option>)}
      </select></label>
      {trend.paused && <span className="fluides-trend__paused" role="status">Flux interrompu / en attente</span>}</div>
    {!values.length ? <div className="fluides-trend__empty">En attente des températures</div>
      : <svg viewBox="0 0 340 330" role="img" aria-label={`Températures CANON et SECTION · ${samples.filter((s) => Number.isFinite(s.canon) || Number.isFinite(s.section)).length} points · degrés Celsius`}>
        <rect data-testid="temperature-plot" x="52" y="22" width="268" height="268" fill="#f4f7f9" stroke="#9cabba" />
        {Array.from({ length: 6 }, (_, i) => {
          const value = low + (high - low) * i / 5;
          return <g key={i}><line x1="52" x2="320" y1={y(value)} y2={y(value)} stroke="#d2dce4" />
            <text x="44" y={y(value) + 4} textAnchor="end">{format(value)}</text></g>;
        })}
        {Array.from({ length: 3 }, (_, i) => {
          const time = start + span * i / 2;
          return <g key={i}><line x1={x(time)} x2={x(time)} y1="22" y2="290" stroke="#d2dce4" />
            <text x={x(time)} y="310" textAnchor={i === 0 ? 'start' : i === 2 ? 'end' : 'middle'}>{clock(time)}</text></g>;
        })}
        <text x="16" y="18">°C</text>
        {['canon', 'section'].map((series) => <g key={series} className={`fluides-trend__${series}`}>
          <path data-testid={`temperature-${series}`} d={temperaturePaths(samples, series, x, y)} fill="none" stroke="currentColor"
            strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" />
          {isolatedTrendSamples(samples, series).map((s) => <circle key={s.time} cx={x(s.time)} cy={y(s[series])} r="1.5" fill="currentColor">
            <title>{series.toUpperCase()} · {format(s[series])} °C · {clock(s.time)}</title></circle>)}
        </g>)}
        <g data-testid="temperature-legend" aria-label="Légende températures">
          <rect x="77" y="30" width="234" height="24" rx="3" fill="#f4f7f9" fillOpacity="0.92" />
          <g className="fluides-trend__canon"><line x1="86" x2="103" y1="43" y2="43" stroke="currentColor" strokeWidth="2.3" /><text x="109" y="47">CANON</text></g>
          <g className="fluides-trend__section"><line x1="188" x2="205" y1="43" y2="43" stroke="currentColor" strokeWidth="2.3" /><text x="211" y="47">SECTION</text></g>
        </g>
      </svg>}
    {trend.error && <p role="status">Historique : {trend.error}</p>}
  </section>;
});

export default function FluidesPanel({ telemetry, trend, windowMinutes, onWindowChange }) {
  const rows = Object.fromEntries(Object.entries(RULES).map(([field, rule]) => [field,
    projectDisplay(rule, telemetry.payload, telemetry.elapsed, telemetry.failure)]));
  const panelName = useAcquisitionPanelName('Fluides');
  return <section className="fluides-panel" aria-label={panelName}>
    <div className="fluides-panel__equipment">
      <section aria-label="Fluides CANON"><h3>CANON</h3><div className="fluides-panel__columns">
        <div>{[15, 14, 13].map((field) => <Indicator key={field} field={field} rows={rows} />)}</div>
        <div>{[11, 12].map((field) => <Indicator key={field} field={field} rows={rows} />)}<Valve name="CANON" telemetry={telemetry} /></div>
      </div><Temperature name="CANON" field={5} rows={rows} telemetry={telemetry} /></section>
      <section aria-label="Fluides SECTION"><h3>SECTION</h3><div className="fluides-panel__columns">
        <div>{[17, 18].map((field) => <Indicator key={field} field={field} rows={rows} />)}
          <div className="fluides-panel__indicator" style={{ backgroundColor: GRAY }} title="Aucun fil de lecture ACQ établi pour ce champ local de Supervision"
            aria-label="EAU FOCALE · non transmise">EAU FOCALE<small>NON TRANSMISE</small></div></div>
        <div>{[0, 1].map((field) => <Indicator key={field} field={field} rows={rows} />)}<Valve name="SECTION" telemetry={telemetry} /></div>
      </div><Temperature name="SECTION" field={22} rows={rows} telemetry={telemetry} /></section>
    </div>
    <div className="fluides-panel__commands"><Command operation="cooling.start" name="Marche refroidissement · désactivé">MARCHE</Command>
      <Command operation="cooling.stop" name="Arrêt refroidissement · désactivé">ARRET</Command></div>
    <FluidesTemperatureChart trend={trend} windowMinutes={windowMinutes} onWindowChange={onWindowChange} />
  </section>;
}
