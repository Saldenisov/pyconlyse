import React, { useMemo } from 'react';
import { DISPLAY_RULES, projectDisplay, pressureConversionDescription } from './elyseLiveProjection';
import PressureReadout from './PressureReadout';
import { temperaturePaths, isolatedTrendSamples } from './fluidesTrend';
import './SupervisionMonitor.css';

const VACUUM = DISPLAY_RULES.filter((rule) => rule.page === 'vide' && rule.kind === 'number');
const COLORS = ['#2767bd', '#a047c3', '#288664', '#d1741d', '#c13d4d', '#577583', '#786634'];

export function VacuumHistoryChart({ telemetry, samples = [], minutes = 30 }) {
  const rows = VACUUM.map((rule) => projectDisplay(rule, telemetry.payload, telemetry.elapsed, telemetry.failure));
  const negative = rows.filter((row) => Number.isFinite(row.value) && row.value < 0).length;
  const zero = rows.filter((row) => row.value === 0).length;
  // Current readouts above still expire on every clock tick. Historical SVG
  // geometry does not depend on telemetry age and need not block those ticks.
  const { hasValues, high, low, ticks, series } = useMemo(() => {
    const end = samples.at(-1)?.time || Date.now();
    const start = end - minutes * 60000;
    const values = samples.flatMap((sample) => VACUUM.map((rule) => sample[rule.id])).filter((v) => Number.isFinite(v) && v > 0);
    const low = values.length ? Math.floor(Math.log10(values.reduce((a, b) => Math.min(a, b)))) - 1 : -10;
    const high = values.length ? Math.max(low + 1, Math.ceil(Math.log10(values.reduce((a, b) => Math.max(a, b))))) : -6;
    const tickStep = Math.max(1, Math.ceil((high - low) / 5));
    const ticks = Array.from({ length: Math.floor((high - low) / tickStep) + 1 }, (_, i) => low + i * tickStep);
    const x = (time) => 48 + (time - start) / (minutes * 60000) * 272;
    const y = (value) => 18 + (high - Math.log10(value)) / (high - low) * 220;
    const series = VACUUM.map((rule) => {
      const points = samples.map((s) => ({ time: s.time, session: s.session,
        value: Number.isFinite(s[rule.id]) && s[rule.id] > 0 ? s[rule.id] : null }));
      return { path: temperaturePaths(points, 'value', x, y),
        markers: isolatedTrendSamples(points, 'value').map((s) => ({ time: s.time, x: x(s.time), y: y(s.value), value: s.value })) };
    });
    return { hasValues: values.length > 0, high, low, ticks, series };
  }, [samples, minutes]);
  return <section className="sup-monitor__vacuum" aria-label="Vide · graphique permanent">
    <h3>Vide · {minutes} min <small>mbar · log</small></h3>
    {(negative > 0 || zero > 0) && <div className="sup-monitor__nonpositive" aria-label="Pressions hors échelle logarithmique"
      title="Valeurs signées conservées dans Dernières pressions. Valeurs ≤ 0 non représentables en logarithme ; vérifier zéro / étalonnage des voies négatives.">
      {negative > 0 && `${negative} négative${negative > 1 ? 's' : ''}`}{negative > 0 && zero > 0 && ' · '}{zero > 0 && `${zero} nulle${zero > 1 ? 's' : ''}`} · hors log
    </div>}
    {!hasValues ? <div className="sup-monitor__waiting">Historique du vide indisponible · aucune courbe inventée</div>
      : <><svg viewBox="0 0 340 278" role="img" aria-label="Historique pression · échelle logarithmique mbar">
        <rect data-testid="vacuum-plot" x="48" y="18" width="272" height="220" fill="#f4f7f9" stroke="#8b9cad" />
        {ticks.map((exponent) => <g key={exponent}><line x1="48" x2="320" y1={18 + (high - exponent) / (high - low) * 220} y2={18 + (high - exponent) / (high - low) * 220} stroke="#d3dde6" />
          <text data-testid="vacuum-log-tick" x="41" y={18 + (high - exponent) / (high - low) * 220 + 3} textAnchor="end">10<tspan baselineShift="super" fontSize="8">{String(exponent).replace('-', '−')}</tspan></text></g>)}
        {[0, 0.5, 1].map((fraction) => <g key={fraction}><line x1={48 + fraction * 272} x2={48 + fraction * 272} y1="18" y2="238" stroke="#d3dde6" />
          <text x={48 + fraction * 272} y="261" textAnchor={fraction === 0 ? 'start' : fraction === 1 ? 'end' : 'middle'}>{fraction === 1 ? '0' : `−${minutes * (1 - fraction)}`} min</text></g>)}
        {VACUUM.map((rule, i) => <g key={rule.id}><path d={series[i].path} fill="none" stroke={COLORS[i % COLORS.length]}
          strokeWidth="1.5" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round"><title>{rule.label}</title></path>
          {series[i].markers.map((point) => <circle key={point.time} cx={point.x} cy={point.y} r="1.5" fill={COLORS[i % COLORS.length]}>
            <title>{rule.label} · {point.value} mbar</title></circle>)}</g>)}
      </svg><div className="sup-monitor__vacuum-legend" aria-label="Courbes de pression">{VACUUM.map((rule, i) => series[i].path && <span key={rule.id} title={rule.label}>
        <i style={{ backgroundColor: COLORS[i % COLORS.length] }} />{rule.label}</span>)}</div></>}
    <details><summary>Dernières pressions</summary><div className="sup-monitor__pressures">{rows.map((row, index) => <div key={row.id}>
      <span style={{ color: COLORS[index % COLORS.length] }}>{row.label}</span>
      <PressureReadout label={`Vide permanent · ${row.label}`} value={row.value} detail={pressureConversionDescription(row, telemetry.payload)} />
    </div>)}</div></details>
  </section>;
}

export default function SupervisionMonitor({ telemetry, vacuumSamples = [], minutes = 30 }) {
  // The current NI1409 bank is metadata, not a qualified image/contour stream.
  // Do not substitute a different experiment's Basler camera or a saved frame.
  return <aside className="sup-monitor" aria-label="Moniteur permanent ELYSE">
    <section className="sup-monitor__camera" aria-label="Image laser permanente">
      <h3>Image laser</h3><div role="img" aria-label="Image laser indisponible · source non connectée">
        <span>IMAGE LASER INDISPONIBLE</span>
      </div>
    </section>
    <section className="sup-monitor__profiles" aria-label="Contours et profils laser permanents">
      <h3>Contours · Profils X / Y</h3><div className="sup-monitor__profile-pair">
        <div role="img" aria-label="Profil X indisponible">X · aucune mesure</div>
        <div role="img" aria-label="Profil Y indisponible">Y · aucune mesure</div>
      </div><p>Centroïde X : — · Y : —</p>
    </section>
    <VacuumHistoryChart telemetry={telemetry} samples={vacuumSamples} minutes={minutes} />
  </aside>;
}
