import React from 'react';
import { DISPLAY_RULES, projectDisplay, readBankField } from './elyseLiveProjection';
import { temperaturePaths, TREND_MAX_POINTS, TREND_WINDOW_MINUTES } from './fluidesTrend';
import panel from './elyseFluidesPanel.json';
import './FluidesPanel.css';

const RULES = Object.fromEntries(DISPLAY_RULES.filter((r) => r.page === 'fluides').map((r) => [r.target_field, r]));
const GRAY = '#88939e';
const format = (value) => Number.isFinite(value) ? value.toFixed(1).replace('.', ',') : '—';

export function fluidesValve(name, telemetry) {
  const spec = panel.valves[name];
  const bits = spec.indices.map((i) => readBankField(telemetry.payload, spec.bank, i, 'boolean', telemetry.elapsed, telemetry.failure));
  const fresh = bits.every((b) => b.quality === 'FRESH');
  const state = fresh ? Number(bits[0].value) + 2 * Number(bits[1].value) : null;
  return { text: fresh ? spec.states[state].text : `VANNE ${name}\nINCONNUE`,
    color: fresh ? spec.states[state].color : GRAY,
    source: `${spec.bank}[${spec.indices.join(', ')}] · ${fresh ? `état ${state}` : bits.find((b) => b.quality !== 'FRESH').quality}` };
}

function Command({ name, children }) {
  return <button type="button" disabled className="fluides-panel__command" aria-label={name}
    title="Lecture seule. Commande uniquement sur le Supervision LabVIEW d’origine.">{children}</button>;
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

function Temperature({ name, field, rows }) {
  const row = rows[field];
  return <div className="fluides-panel__temperature">
    <div><Command name={`Diminuer consigne ${name} · désactivé`}>◀</Command>
      <Command name={`Augmenter consigne ${name} · désactivé`}>▶</Command></div>
    <span>T° {name} :</span>
    <span className="fluides-panel__setpoint" title="Consigne locale au PC Supervision, non transmise par ACQ">— °C <small>consigne non transmise</small></span>
    <span className="fluides-panel__reading" title={`${row.bank}[${row.index}] · ${row.quality}`}>
      <output aria-label={`Température ${name} · lecture`}>{format(row.value)}</output> °C
      <small>mesure · {row.quality === 'FRESH' ? 'récente' : row.quality}</small></span>
  </div>;
}

export function FluidesTemperatureChart({ trend }) {
  const samples = trend.samples;
  const values = samples.flatMap((s) => [s.canon, s.section]).filter(Number.isFinite);
  const end = samples[samples.length - 1]?.time;
  const span = Math.max(60000, end - samples[0]?.time || 0);
  const start = end - span;
  const min = Math.min(...values), max = Math.max(...values);
  const pad = Math.max(0.2, (max - min) * 0.15);
  const low = Math.floor((min - pad) * 10) / 10;
  const high = Math.ceil((max + pad) * 10) / 10;
  const x = (t) => 68 + (t - start) / span * 684;
  const y = (v) => 24 + (high - v) / (high - low) * 228;
  const clock = (t) => new Date(t).toLocaleTimeString('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  return <section className="fluides-trend" aria-label="Températures CANON et SECTION">
    <div className="fluides-trend__header"><h3>Températures CANON + SECTION</h3>
      <span className={trend.paused ? 'fluides-trend__paused' : ''}>{trend.paused ? 'Flux interrompu / en attente' : 'Mesures en direct'}</span></div>
    <div className="fluides-trend__legend"><span className="fluides-trend__canon">● CANON · C1[0]</span>
      <span className="fluides-trend__section">● SECTION · C1[8]</span><span>Échelle commune · °C</span></div>
    {!values.length ? <div className="fluides-trend__empty">En attente des premières températures valides · aucune valeur inventée</div>
      : <svg viewBox="0 0 790 300" role="img" aria-label={`Températures CANON et SECTION · ${samples.filter((s) => Number.isFinite(s.canon) || Number.isFinite(s.section)).length} points · degrés Celsius`}>
        <rect x="68" y="24" width="684" height="228" fill="#f4f7f9" stroke="#9cabba" />
        {Array.from({ length: 6 }, (_, i) => {
          const value = low + (high - low) * i / 5;
          return <g key={i}><line x1="68" x2="752" y1={y(value)} y2={y(value)} stroke="#d2dce4" />
            <text x="58" y={y(value) + 4} textAnchor="end">{format(value)}</text></g>;
        })}
        {Array.from({ length: 5 }, (_, i) => {
          const time = start + span * i / 4;
          return <g key={i}><line x1={x(time)} x2={x(time)} y1="24" y2="252" stroke="#d2dce4" />
            <text x={x(time)} y="274" textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}>{clock(time)}</text></g>;
        })}
        <text x="16" y="18">°C</text>
        {['canon', 'section'].map((series) => <g key={series} className={`fluides-trend__${series}`}>
          <path data-testid={`temperature-${series}`} d={temperaturePaths(samples, series, x, y)} fill="none" stroke="currentColor" strokeWidth="2.3" />
          {samples.filter((s) => Number.isFinite(s[series])).map((s) => <circle key={s.time} cx={x(s.time)} cy={y(s[series])} r="2.5" fill="currentColor">
            <title>{series.toUpperCase()} · {format(s[series])} °C · {clock(s.time)}</title></circle>)}
        </g>)}
      </svg>}
    <p>Dernières {TREND_WINDOW_MINUTES} min · maximum {TREND_MAX_POINTS} points · lecture navigateur ≈ 1 s · heure de réception Everest (Paris).
      Les interruptions restent des trous, pas des zéros. Buffer RAM de cette session d’affichage ; aucun fichier ni base de données.</p>
  </section>;
}

export default function FluidesPanel({ telemetry, trend }) {
  const rows = Object.fromEntries(Object.entries(RULES).map(([field, rule]) => [field,
    projectDisplay(rule, telemetry.payload, telemetry.elapsed, telemetry.failure)]));
  return <section className="fluides-panel" aria-label="Fluides · lecture seule">
    <div className="fluides-panel__notice">LECTURE SEULE · palette et états repris du VI · aucune commande matérielle.</div>
    <h3>Régulation de température du CANON et de la SECTION</h3>
    <div className="fluides-panel__equipment">
      <section aria-label="Fluides CANON"><div className="fluides-panel__columns">
        <div>{[15, 14, 13].map((field) => <Indicator key={field} field={field} rows={rows} />)}</div>
        <div>{[11, 12].map((field) => <Indicator key={field} field={field} rows={rows} />)}<Valve name="CANON" telemetry={telemetry} /></div>
      </div><Temperature name="CANON" field={5} rows={rows} /></section>
      <section aria-label="Fluides SECTION"><div className="fluides-panel__columns">
        <div>{[17, 18].map((field) => <Indicator key={field} field={field} rows={rows} />)}
          <div className="fluides-panel__indicator" style={{ backgroundColor: GRAY }} title="Aucun fil de lecture ACQ établi pour ce champ local de Supervision"
            aria-label="EAU FOCALE · non transmise">EAU FOCALE<small>NON TRANSMISE</small></div></div>
        <div>{[0, 1].map((field) => <Indicator key={field} field={field} rows={rows} />)}<Valve name="SECTION" telemetry={telemetry} /></div>
      </div><Temperature name="SECTION" field={22} rows={rows} /></section>
    </div>
    <div className="fluides-panel__commands"><Command name="Marche refroidissement · désactivé">MARCHE</Command>
      <Command name="Arrêt refroidissement · désactivé">ARRET</Command></div>
    <p className="fluides-panel__limits">Consignes du PC Supervision et champ « Eau Foc défauts » non transmis ici : affichés inconnus, jamais remplacés par les valeurs sauvegardées du VI.
      Couleur reproduite ≠ confirmation physique ou autorisation de chauffe.</p>
    <FluidesTemperatureChart trend={trend} />
    <details className="fluides-panel__sources"><summary>Sources et états des vannes</summary>
      <p>CANON : C3_IN_DIO96[2, 3] · SECTION : C3_IN_DIO96[8, 9]. Bit fermé + 2 × bit ouvert :
        0 = REGULATION (vert), 1 = FERMEE (orange), 2 = OUVERTE (orange), 3 = EN DEFAUT (rouge).</p>
      <p>Températures : C1NI6071E[0, 8]. Indicateurs directs : six bits C3 et trois bits C4. Les palettes TRUE/FALSE sont propres à chaque champ du VI.</p>
    </details>
  </section>;
}
