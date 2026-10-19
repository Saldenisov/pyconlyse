import React from 'react';
import { DISPLAY_RULES, projectDisplay } from './elyseLiveProjection';
import panel from './elyseModulatorPanel.json';
import './ModulatorPanel.css';

const RULES = Object.fromEntries(DISPLAY_RULES.filter((r) => r.page === 'modulateur').map((r) => [r.target_field, r]));
const STAGES = [['GENERAL', 54], ['CHAUFFAGE', 55], ['PREMA', 56], ['FOCALES', 58], ['RELAIS HT', 57]];
const LABELS = {
  7: 'Contact\nPerche de masse', 8: 'Sécurité\nThyratron', 9: 'Contact\nPorte Cabine',
  10: 'Temporisation', 11: 'Ventilation\nThyratron', 12: 'Résistivité',
  13: 'Contact capot\ncuve Klystron', 14: "Niveau d’huile\nCuve Klystron", 15: 'EAU focale\nKlystron',
  16: 'EAU corps\nKlystron', 17: 'EAU collecteur\nKlystron', 18: 'EAU Cuve\nKlystron',
  19: 'EAU CANON', 20: 'Vide Klystron', 45: 'EAU SECTION',
  24: 'Mesure V LAR', 25: 'I Fin de ligne', 26: 'I Thyratron',
  27: 'V Chauffage\nThyratron', 28: 'I Chauffage\nThyratron', 29: 'I Réservoir\nThyratron',
  30: 'Courant de\nPrémagnétisation', 0: 'I Focale 1\nKlystron', 1: 'I Focale 2\nKlystron',
  2: 'I Focale 3\nKlystron', 3: 'I Chauffage\nKlystron', 4: 'V Chauffage\nKlystron',
  5: 'V Klystron', 6: 'I Klystron',
};
// Numeric precision follows the visible Supervision layout. Saved formats,
// including LabVIEW-specific %g rendering, remain available as provenance.
const THYRATRON = [[37, 30, 1], [36, 29, 1], [34, 27, 2], [35, 28, 2], [31, 24, 1], [32, 25, 1], [33, 26, 2]];
const KLYSTRON = [[39, 5, 1], [38, 6, 1], [41, 4, 1], [40, 3, 1], [42, 0, 2], [43, 1, 2], [44, 2, 2]];

export function indicatorStyle(row, palette) {
  const fresh = row?.quality === 'FRESH' && typeof row.value === 'boolean';
  return { backgroundColor: fresh ? row.value ? palette.true_color : palette.false_color : '#88939e' };
}

function sourceTitle(row) {
  return `${row.bank}[${row.index}] = ${row.value === null ? 'INCONNU' : String(row.value)} · ${row.quality}`;
}

function DisabledCommand({ children, name }) {
  return <button type="button" disabled className="modulator-panel__command" aria-label={name}
    title="Lecture seule ici. Commande uniquement sur le Supervision LabVIEW d’origine.">{children}</button>;
}

function Indicator({ field, rows }) {
  const row = rows[field];
  return <div className="modulator-panel__indicator" style={indicatorStyle(row, panel.fields[field])}
    title={sourceTitle(row)} aria-label={`${row.label} · ${row.value === null ? 'inconnu' : String(row.value)}`}>
    {LABELS[field] || row.label}
  </div>;
}

function Measurement({ numeric, status, decimals, rows }) {
  const row = rows[numeric];
  const fresh = row.quality === 'FRESH' && row.value !== null;
  return <div className={`modulator-panel__measurement${fresh ? '' : ' modulator-panel__measurement--unknown'}`}>
    <Indicator field={status} rows={rows} />
    <div className="modulator-panel__number" title={`${sourceTitle(row)} · format VI ${panel.fields[numeric].saved_format}`}>
      <output aria-label={row.label}>{fresh ? row.value.toFixed(decimals).replace('.', ',') : '—'}</output>
      <span>{row.unit}</span>
    </div>
  </div>;
}

export default function ModulatorPanel({ telemetry }) {
  const rows = Object.fromEntries(Object.entries(RULES).map(([index, rule]) => [index,
    projectDisplay(rule, telemetry.payload, telemetry.elapsed, telemetry.failure)]));
  const sourceBanks = ['C2NI6071E', 'C4_IN_DIO96', 'EPS'];
  const ages = sourceBanks.map((bank) => telemetry.payload?.snapshot?.publications?.[bank]?.age_seconds);
  const maxAge = ages.every(Number.isFinite) ? Math.max(...ages) + telemetry.elapsed : null;
  return <section className="modulator-panel" aria-label="Modulateur · lecture seule">
    <div className="modulator-panel__sheet">
      <section className="modulator-panel__half modulator-panel__half--mod"><h3>MODULATEUR</h3>
        <div className="modulator-panel__mod-layout">
          <fieldset className="modulator-panel__stages"><legend>Étapes logicielles · EPS</legend>
            {STAGES.map(([name, field]) => <div className="modulator-panel__stage" key={field}>
              <span className="modulator-panel__lamp" style={indicatorStyle(rows[field], panel.fields[field])}
                title={sourceTitle(rows[field])} role="img" aria-label={`${name} · ${rows[field].value === null ? 'inconnu' : rows[field].value ? 'ON' : 'OFF'}`} />
              <DisabledCommand name={`Marche ${name} · commande désactivée`}>M</DisabledCommand>
              <strong>{name}</strong>
              <DisabledCommand name={`Arrêt ${name} · commande désactivée`}>A</DisabledCommand>
            </div>)}
            <DisabledCommand name="RESET Modulateur · commande désactivée">RESET</DisabledCommand>
          </fieldset>
          <div className="modulator-panel__interlocks" aria-label="Indicateurs Thyratron">
            {[11, 9, 8, 7, 10].map((field) => <Indicator key={field} field={field} rows={rows} />)}
          </div>
          <div className="modulator-panel__measurements" aria-label="Mesures Thyratron">
            {THYRATRON.map(([numeric, status, decimals]) => <Measurement key={numeric} {...{ numeric, status, decimals, rows }} />)}
          </div>
        </div>
      </section>
      <section className="modulator-panel__half modulator-panel__half--kly"><h3>KLYSTRON</h3>
        <div className="modulator-panel__kly-layout">
          <div className="modulator-panel__water" aria-label="Indicateurs eau et Klystron">
            <div>{[12, 45, 19, 17, 16].map((field) => <Indicator key={field} field={field} rows={rows} />)}</div>
            <div>{[15, 18, 13, 20, 14].map((field) => <Indicator key={field} field={field} rows={rows} />)}</div>
          </div>
          <div className="modulator-panel__measurements" aria-label="Mesures Klystron">
            {KLYSTRON.map(([numeric, status, decimals]) => <Measurement key={numeric} {...{ numeric, status, decimals, rows }} />)}
          </div>
        </div>
      </section>
    </div>
    <details className="modulator-panel__sources"><summary>Sources des 48 indicateurs et mesures</summary>
      <p>LECTURE SEULE · M / A et RESET sur Supervision LabVIEW.
        Âge C2 / C4 / EPS : {maxAge === null ? '—' : `${maxAge.toFixed(1)} s`}</p>
      <p>Couleurs de la palette enregistrée du VI : bits C4 FALSE → vert, TRUE → rouge.
        Lampes d’étape : EPS OFF → vert sombre, ON → vert vif. Gris = lecture absente, périmée ou erronée.
        Couleur reproduite ≠ autorisation matérielle. Transitions réelles à confirmer avec l’opérateur.</p>
      <table><thead><tr><th>Affichage</th><th>Source</th><th>Valeur</th><th>Qualité</th></tr></thead>
        <tbody>{Object.values(rows).map((row) => <tr key={row.id}>
          <th scope="row">{row.label}</th><td>{row.bank}[{row.index}]</td><td>{row.value === null ? '—' : String(row.value)}</td><td>{row.quality}</td>
        </tr>)}</tbody></table>
    </details>
  </section>;
}
