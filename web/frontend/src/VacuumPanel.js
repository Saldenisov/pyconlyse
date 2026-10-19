import React from 'react';
import { DISPLAY_RULES, projectDisplay, readBankField } from './elyseLiveProjection';
import PressureReadout from './PressureReadout';
import layout from './elyseVacuumPanel.json';
import './VacuumPanel.css';

const RULES = Object.fromEntries(DISPLAY_RULES.filter((r) => r.page === 'vide').map((r) => [r.target_field, r]));
const QUALITY = { FRESH: 'Récent', STALE: 'Périmé', MISSING: 'Absent', READ_ERROR: 'Erreur lecture',
  SCHEMA_ERROR: 'Schéma différent', VALUE_ERROR: 'Valeur invalide', UNAVAILABLE: 'Indisponible' };

export function nativePlacement(item, width = layout.pressure_width) {
  return { left: `${item.x / layout.canvas_width * 100}%`, top: `${item.y * 1.35}px`,
    width: `${width / layout.canvas_width * 100}%` };
}

export function projectVacuumValve(spec, telemetry) {
  const bits = spec.indices.map((i) => readBankField(telemetry.payload, spec.bank, i, 'boolean', telemetry.elapsed, telemetry.failure));
  const fresh = bits.every((bit) => bit.quality === 'FRESH');
  const state = fresh ? Number(bits[0].value) + 2 * Number(bits[1].value) : null;
  return { text: fresh ? spec.states[state].text : `VANNE ${spec.name}\nINCONNUE`,
    color: fresh ? spec.states[state].color : '#88939e',
    quality: fresh ? 'FRESH' : bits.find((bit) => bit.quality !== 'FRESH').quality,
    source: `${spec.bank}[${spec.indices.join(', ')}]`, state };
}

export default function VacuumPanel({ telemetry }) {
  return <section className="vacuum-layout" aria-label="Vide · implantation des capteurs">
    <div className="vacuum-layout__heading"><h3>Vide · implantation des capteurs</h3><span>Disposition Supervision · lecture seule</span></div>
    <div className="vacuum-layout__scroll"><div className="vacuum-layout__canvas" aria-label="Disposition spatiale du vide">
      {layout.pressures.map((place) => {
        const row = projectDisplay(RULES[place.field], telemetry.payload, telemetry.elapsed, telemetry.failure);
        return <div key={place.field} data-testid={`vacuum-location-${place.field}`}
          className={`vacuum-layout__pressure vacuum-layout__pressure--${row.quality.toLowerCase()}`}
          style={nativePlacement(place)} title={`${row.bank}[${row.index}] · ${row.quality} · contrôle VI ${place.control_uid}`}>
          <span className="vacuum-layout__label">{row.label}</span>
          <PressureReadout value={row.value} label={row.label} />
          <small>{QUALITY[row.quality] || row.quality}{Number.isFinite(row.age) && ` · ${row.age.toFixed(1)} s`}
            {row.native_filter_samples > 1 && <span className="vacuum-layout__instant"> · sans moyenne native</span>}</small>
        </div>;
      })}
      {layout.valves.map((spec) => {
        const valve = projectVacuumValve(spec, telemetry);
        return <div key={spec.name} className="vacuum-layout__valve"
          style={{ ...nativePlacement(spec, 87), backgroundColor: valve.color }}
          aria-label={valve.text.replace('\n', ' · ')} title={`${valve.source} · ${valve.quality} · état VI ${valve.state ?? 'inconnu'}`}>
          {valve.text}
        </div>;
      })}
    </div></div>
    <p className="vacuum-layout__note">Positions relatives conservées, pas à l’échelle. Aucun réarrangement des capteurs sur petit écran : défilement horizontal si nécessaire.
      Fonds des mesures neutres : les alarmes pression ne sont pas qualifiées. Couleurs des deux vannes reprises des bits C5, pas une autorisation matérielle.</p>
    <details className="vacuum-layout__sources"><summary>Sources des mesures et des vannes</summary>
      <div>{layout.pressures.map((place) => {
        const rule = RULES[place.field];
        return <span key={place.field}>{rule.label} : {rule.bank}[{rule.index}]</span>;
      })}</div>
      <p>CATHODE : C5_IN_DIO96[15, 14] · INJECTION : C5_IN_DIO96[17, 16]. Code = premier bit + 2 × second bit.
        0 : ENTROUVERTE ; 1 : OUVERTE ; 2 : FERMEE ; 3 : EN DEFAUT. Les noms des contacts ne remplacent pas la polarité câblée du VI.</p>
    </details>
  </section>;
}
