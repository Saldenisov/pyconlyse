import React, { useEffect, useState } from 'react';
import { ACQ_TIMING, DISPLAY_RULES, formatDisplay, projectDisplay } from './elyseLiveProjection';
import ModulatorPanel from './ModulatorPanel';
import FluidesPanel from './FluidesPanel';
import SynchronizationEditor from './SynchronizationEditor';
import SupervisionSynchronization from './components/SupervisionSynchronization';
import { emptyTrend, nextFluidesTrend } from './fluidesTrend';
import PressureReadout from './PressureReadout';
import VacuumPanel from './VacuumPanel';
import { MachineControlPanel, RadioprotectionPanel, HighTensionPanel, HighFrequencyPanel, PowerSuppliesPanel } from './SupervisionControlPanels';
import { useRadioprotectionLog } from './radioprotectionLog';
import useAcquisitionTelemetry from './useAcquisitionTelemetry';
import { BeamLinePanel, SynopticPanel, NewFocusPanel, EthernetCameraPanel } from './SupervisionWorkspace';
import './LiveSupervision.css';

const CONTROL_PAGES = ['machine', 'radioprotection', 'ht', 'hf', 'alimentations', 'voie-directe', 'voie-deviee', 'synoptique', 'newfocus', 'camera'];
const INDEPENDENT_PAGES = ['synoptique', 'newfocus', 'camera'];
function ValueCard({ row }) {
  const pressure = row.unit === 'mbar';
  return <div className={`elyse-live__card elyse-live__card--${row.quality.toLowerCase()}${pressure ? ' elyse-live__card--pressure' : ''}`}>
    <span className="elyse-live__label">{row.label}</span>
    {pressure ? <PressureReadout value={row.value} label={row.label} />
      : <div><output aria-label={row.label}>{formatDisplay(row.value, row.unit)}</output> <span>{row.unit}</span></div>}
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

export default function LiveSupervision({ tab, client, telemetry: sharedTelemetry, displayHistory }) {
  const localTelemetry = useAcquisitionTelemetry(client, sharedTelemetry === undefined);
  const telemetry = sharedTelemetry === undefined ? localTelemetry : sharedTelemetry;
  const { payload, failure, elapsed } = telemetry;
  useRadioprotectionLog(telemetry);
  const [fluidesTrend, setFluidesTrend] = useState(emptyTrend);
  const [windowMinutes, setWindowMinutes] = useState(() => {
    try { const saved = Number(window.localStorage.getItem('elyse.fluides.windowMinutes')); return [5, 15, 30, 60, 120].includes(saved) ? saved : 30; }
    catch { return 30; }
  });
  const changeWindow = (minutes) => {
    setWindowMinutes(minutes);
    try { window.localStorage.setItem('elyse.fluides.windowMinutes', String(minutes)); } catch { /* Display preference only. */ }
  };
  useEffect(() => {
    setFluidesTrend((old) => nextFluidesTrend(old, { payload, failure, elapsed }, Date.now(), windowMinutes));
  }, [payload, failure, elapsed, windowMinutes]);
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
      : tab === 'fluides' ? <FluidesPanel telemetry={telemetry} trend={displayHistory || fluidesTrend}
        windowMinutes={displayHistory?.minutes || windowMinutes} onWindowChange={displayHistory?.changeMinutes || changeWindow} />
      : tab === 'vide' ? <VacuumPanel telemetry={telemetry} />
      : tab === 'machine' ? <MachineControlPanel telemetry={telemetry} />
      : tab === 'radioprotection' ? <RadioprotectionPanel telemetry={telemetry} />
      : tab === 'ht' ? <HighTensionPanel telemetry={telemetry} />
      : tab === 'hf' ? <HighFrequencyPanel telemetry={telemetry} />
      : tab === 'alimentations' ? <PowerSuppliesPanel telemetry={telemetry} />
      : tab === 'voie-directe' ? <BeamLinePanel line="direct" telemetry={telemetry} />
      : tab === 'voie-deviee' ? <BeamLinePanel line="deviated" telemetry={telemetry} />
      : tab === 'synoptique' ? <SynopticPanel />
      : tab === 'newfocus' ? <NewFocusPanel />
      : tab === 'camera' ? <EthernetCameraPanel />
      : tab === 'synchro' ? <><SupervisionSynchronization /><SynchronizationEditor telemetry={telemetry} client={client} /></>
      : <Group title={tab === 'synchro' ? 'Paramètres synchronisation ACQ' : 'Mesures'} rules={measures} telemetry={telemetry} />}
    {!['modulateur', 'fluides', ...CONTROL_PAGES].includes(tab) && <>
      <Group title="Entrées logiques · bits bruts" rules={bits} telemetry={telemetry} />
      <Group title="Étapes logicielles · EPS" rules={software} telemetry={telemetry} /></>}
  </div>;
}
