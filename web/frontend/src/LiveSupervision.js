import React, { useEffect, useState } from 'react';
import { ACQ_TIMING, DISPLAY_RULES, formatDisplay, projectDisplay } from './elyseLiveProjection';
import ModulatorPanel from './ModulatorPanel';
import FluidesPanel from './FluidesPanel';
import { emptyTrend, nextFluidesTrend, TREND_WINDOW_MINUTES } from './fluidesTrend';
import PressureReadout from './PressureReadout';
import VacuumPanel from './VacuumPanel';
import { RadioprotectionPanel, HighTensionPanel, HighFrequencyPanel, PowerSuppliesPanel } from './SupervisionControlPanels';
import { useRadioprotectionLog } from './radioprotectionLog';
import useAcquisitionTelemetry from './useAcquisitionTelemetry';
import { BeamLinePanel, SynopticPanel, NewFocusPanel, EthernetCameraPanel } from './SupervisionWorkspace';
import './LiveSupervision.css';

const QUALITY = { FRESH: 'Récent', STALE: 'Périmé', MISSING: 'Absent', WAITING: 'En attente',
  UNAVAILABLE: 'Indisponible', READ_ERROR: 'Erreur lecture', SCHEMA_ERROR: 'Schéma différent',
  VALUE_ERROR: 'Valeur invalide', UNQUALIFIED: 'Non qualifié' };
const CONTROL_PAGES = ['radioprotection', 'ht', 'hf', 'alimentations', 'voie-directe', 'voie-deviee', 'synoptique', 'newfocus', 'camera'];
const INDEPENDENT_PAGES = ['synoptique', 'newfocus', 'camera'];
const GAPS = {
  vide: 'Implantation reprise de la page Vide originale. MIROIR et DIPOLE 1 : conversion instantanée, sans la moyenne native de 30 échantillons. Alarmes pression non qualifiées ; vannes C5 projetées selon les quatre cas du VI.',
  fluides: `Palettes du VI et quatre états des vannes projetés depuis les entrées C3. Consignes locales Supervision et Eau Foc non transmis. Courbes CANON / SECTION : buffer RAM limité à ${TREND_WINDOW_MINUTES} min, sans archivage.`,
  modulateur: 'Palette enregistrée du VI et flags EPS, pas autorisation de démarrage. Concordance des transitions réelles à vérifier avec l’opérateur.',
  radioprotection: 'Douze états C4, textes et palettes du VI. Console locale : différences de snapshots, pas journal natif ni permission de tir.',
  ht: 'Sept états C4 et trois lectures C2. Consignes locales, préampli et alarme pression SECTION non qualifiés. Aucune commande disponible.',
  hf: 'Atténuation log10/cos et phases : formules natives. Neuf états locaux et consignes non qualifiés. Aucun défaut supposé absent.',
  synchro: 'Paramètres C10 du PC Acquisition uniquement, pas mesure physique. C11 Supervision : la copie locale ACQ diffère de l’écran distant ; valeurs exclues.',
  'voie-directe': 'Onze blocs natifs. Consigne ACQ et Lecture distinctes ; commandes et trois voyants par bloc non qualifiés.',
  'voie-deviee': 'Neuf blocs natifs. H5/V5 : lecture commune C1[34] conservée ; C6[8] reste Réserve dans la carte.',
  synoptique: 'Image PNG originale extraite à l’identique du VI. Schéma statique, sans verdict matériel.',
  newfocus: 'Préparation locale du DS_Picomotor8742 existant. Aucun scan, connexion ou mouvement. Identité et axes physiques à confirmer.',
  camera: 'Caméra Ethernet future. Aucun pilote IMAQ, connexion, image ou mesure simulée.',
  alimentations: 'Premier voyant : AND/OR de 16 entrées C3 inversées, quatre cas du VI. Calcul sur un snapshot : décalage natif entre frames non reproduit. Voyant de défaut séparé non qualifié.',
};

function ValueCard({ row }) {
  const source = `${row.bank}[${row.index}]`;
  const pressure = row.unit === 'mbar';
  const formula = row.transform === 'offset_gain'
    ? `(x − ${row.offset}) × ${row.scale}` : row.transform === 'phase_polynomial'
      ? '1.1309x³ − 5.746x² − 40.368x + 102.28' : row.scale ? `x × ${row.scale}` : 'Valeur directe';
  return <div className={`elyse-live__card elyse-live__card--${row.quality.toLowerCase()}${pressure ? ' elyse-live__card--pressure' : ''}`}>
    <span className="elyse-live__label">{row.label}</span>
    {pressure ? <PressureReadout value={row.value} label={row.label} />
      : <div><output aria-label={row.label}>{formatDisplay(row.value, row.unit)}</output> <span>{row.unit}</span></div>}
    <details><summary>{source}</summary><small>{QUALITY[row.quality]}{row.age !== undefined && row.age !== null && ` · ${row.age.toFixed(1)} s`}
      {row.native_filter_samples > 1 && ' · sans moyenne native'}<br />{formula}<br />
      {row.role === 'software_flag' ? 'Flag logiciel EPS, pas entrée physique.' : row.role === 'configured'
        ? 'Paramètre configuré, pas signal physique mesuré.' : 'Valeur du contrôle LabVIEW.'}
      {row.source_terminal && <><br />Fil {row.source_terminal} → {row.target_terminal}</>}</small></details>
  </div>;
}

function Group({ title, rules, telemetry }) {
  if (!rules.length) return null;
  const vacuum = rules.every((rule) => rule.unit === 'mbar');
  return <section className={`elyse-live__group${vacuum ? ' elyse-live__group--vacuum' : ''}`} aria-label={title}>
    <h3>{title}{vacuum && <span className="elyse-pressure__heading-note">mbar · 1 décimale</span>}</h3><div className="elyse-live__grid">
    {rules.map((rule) => <ValueCard key={rule.id} row={projectDisplay(rule,
      telemetry.payload, telemetry.elapsed, telemetry.failure)} />)}
  </div></section>;
}

export default function LiveSupervision({ tab, client, telemetry: sharedTelemetry }) {
  const localTelemetry = useAcquisitionTelemetry(client, sharedTelemetry === undefined);
  const telemetry = sharedTelemetry === undefined ? localTelemetry : sharedTelemetry;
  const { payload, failure, elapsed } = telemetry;
  useRadioprotectionLog(telemetry);
  const [fluidesTrend, setFluidesTrend] = useState(emptyTrend);
  useEffect(() => {
    setFluidesTrend((old) => nextFluidesTrend(old, { payload, failure, elapsed }, Date.now()));
  }, [payload, failure, elapsed]);
  const banks = Object.values(payload?.snapshot?.publications || {});
  const stale = banks.some((bank) => bank.stale !== false || !Number.isFinite(bank.age_seconds)
    || bank.age_seconds + elapsed >= 2);
  const quality = failure ? 'UNAVAILABLE' : stale ? 'STALE' : payload?.quality || 'WAITING';
  const alarm = quality === 'FRESH' || quality === 'WAITING' ? null
    : quality === 'STALE' ? 'Télémétrie périmée' : 'Télémétrie indisponible';
  const rules = tab === 'synchro' ? ACQ_TIMING : DISPLAY_RULES.filter((r) => r.page === tab);
  const measures = rules.filter((r) => r.kind === 'number');
  const bits = rules.filter((r) => r.kind === 'boolean' && r.bank !== 'EPS');
  const software = rules.filter((r) => r.bank === 'EPS');
  return <div className="elyse-live" aria-label="Affichage télémétrie Supervision">
    {alarm && !INDEPENDENT_PAGES.includes(tab) && <div className="elyse-live__alarm" role="alert">{alarm}</div>}
    {tab === 'modulateur' ? <ModulatorPanel telemetry={telemetry} />
      : tab === 'fluides' ? <FluidesPanel telemetry={telemetry} trend={fluidesTrend} />
      : tab === 'vide' ? <VacuumPanel telemetry={telemetry} />
      : tab === 'radioprotection' ? <RadioprotectionPanel telemetry={telemetry} />
      : tab === 'ht' ? <HighTensionPanel telemetry={telemetry} />
      : tab === 'hf' ? <HighFrequencyPanel telemetry={telemetry} />
      : tab === 'alimentations' ? <PowerSuppliesPanel telemetry={telemetry} />
      : tab === 'voie-directe' ? <BeamLinePanel line="direct" telemetry={telemetry} />
      : tab === 'voie-deviee' ? <BeamLinePanel line="deviated" telemetry={telemetry} />
      : tab === 'synoptique' ? <SynopticPanel />
      : tab === 'newfocus' ? <NewFocusPanel />
      : tab === 'camera' ? <EthernetCameraPanel />
      : <Group title={tab === 'synchro' ? 'Paramètres synchronisation ACQ' : 'Mesures'} rules={measures} telemetry={telemetry} />}
    {!['modulateur', 'fluides', ...CONTROL_PAGES].includes(tab) && <>{bits.length > 0 && <p>TRUE/FALSE = bits du programme. Couleurs et sens physique non qualifiés.</p>}
      <Group title="Entrées logiques · bits bruts" rules={bits} telemetry={telemetry} />
      <Group title="Étapes logicielles · EPS" rules={software} telemetry={telemetry} /></>}
    {tab !== 'vide' && !CONTROL_PAGES.includes(tab) && <Group title="Vide · dernières valeurs" rules={DISPLAY_RULES.filter((r) => r.page === 'vide')} telemetry={telemetry} />}
    <details className="elyse-live__provenance"><summary>Provenance et limites</summary>
      <p>{QUALITY[quality] || quality} · 10.20.30.10 → Python 3.4 → Everest · lecture seule · {banks.length}/27 banques · actualisation 1 s</p>
      {failure && <p>{failure} · aucune ancienne valeur présentée comme actuelle.</p>}
      <p>Valeurs LabVIEW, non atomiques. Ni commande, ni autorisation matérielle. Aucune écriture sur disque ; courbes Fluides limitées à {TREND_WINDOW_MINUTES} min en RAM.</p>
      <p>{GAPS[tab]}</p>
      <p>Projection statique des fils du VI original ; concordance complète avec Supervision non certifiée.
        L’état ON du récepteur ne prouve pas l’état des cartes. Un contrôle LabVIEW récent peut contenir une ancienne valeur instrumentale.
        Les paramètres propres au PC Supervision ne sont pas supposés connus depuis la copie ACQ.</p>
      <span>Session récepteur : {payload?.snapshot?.receiver_session || '—'}</span>
    </details>
  </div>;
}
