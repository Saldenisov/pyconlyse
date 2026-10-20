import React, { useEffect, useRef, useState } from 'react';
import { elyseSupervisionClient } from './api/elyseSupervisionClient';
import ElyseBeamline from './ElyseBeamline';
import ElyseMotion from './ElyseMotion';
import ElyseSupervisionBusiness from './ElyseSupervisionBusiness';
import AcqTelemetry from './AcqTelemetry';
import AcqRuntime from './AcqRuntime';
import LiveSupervision from './LiveSupervision';
import useAcquisitionTelemetry from './useAcquisitionTelemetry';
import { AcquisitionWatchdog, MachineFrequency } from './SupervisionHeader';
import { BeamLinePanel, SynopticPanel, NewFocusPanel, EthernetCameraPanel } from './SupervisionWorkspace';
import './Elyse.css';

const TABS = [['vide', 'Vide'], ['synchro', 'Synchro'],
  ['fluides', 'Fluides'], ['modulateur', 'Modulateur'], ['radioprotection', 'Radioprotection'],
  ['ht', 'HT'], ['hf', 'HF'], ['alimentations', 'Alimentations'],
  ['voie-directe', 'Voie directe'], ['voie-deviee', 'Voie déviée'], ['synoptique', 'Synoptique ELYSE'],
  ['newfocus', 'NewFocus'], ['camera', 'Caméra Ethernet'], ['business', 'Supervision / ACQ'],
  ['telemetry', 'Télémétrie 10.20.30.10'], ['acq-runtime', 'Python Acquisition']];

function Lamp() {
  return <span className="elyse-lamp elyse-lamp--unknown" aria-hidden="true" title="Télémétrie indisponible" />;
}
function Panel({ title, className = '', children }) {
  return <section className={`elyse-panel ${className}`}><div className="elyse-panel__title">{title}</div>
    <div className="elyse-panel__body">{children}</div></section>;
}
function Readout({ label, unit = '' }) {
  return <div className="elyse-readout"><span className="elyse-readout__label">{label}</span>
    <output className="elyse-readout__value" title="Aucune mesure connectée">—</output><span>{unit}</span></div>;
}
function HardwareButton({ children }) {
  return <button type="button" disabled className="elyse-hardware-button"
    title="Matériel non connecté : aucune commande possible">{children}</button>;
}
function Trend({ label }) {
  return <div className="elyse-trend-placeholder" role="img" aria-label={label}>{label}</div>;
}
function Flags({ names = [] }) {
  return <div className="elyse-status-list">{names.map((name) =>
    <div className="elyse-status-line" key={name}><Lamp /><span>{name}</span><strong>—</strong></div>)}</div>;
}
function finiteDraft(value) {
  if (typeof value !== 'string' || !value.trim() || !Number.isFinite(Number(value))) {
    throw new Error('Valeur numérique explicite requise pour le brouillon.');
  }
  return Number(value);
}

function ModelControls({ config, context, pageKey }) {
  if (!config) return <div className="elyse-empty-view">Modèles Python indisponibles</div>;
  const { dps, drafts, setDrafts, run, pending } = context;
  const groups = [...new Set(config.arrows.map((r) => r.numeric_field))];
  const submit = async (rule, procedure) => {
    const arrows = Object.fromEntries(config.arrows.map((r) => [r.arrow, false]));
    const procedures = Object.fromEntries(config.procedures.map((name) => [name, false]));
    const numeric = {};
    if (rule) {
      arrows[rule.arrow] = true;
      numeric[rule.numeric_field] = finiteDraft(drafts[`${pageKey}:${rule.numeric_field}`]);
    }
    if (procedure) procedures[procedure] = true;
    const inputs = config.arrows.length
      ? { page: config.page, current_dps: dps, arrows, procedures, numeric_newval: numeric }
      : { page: config.page, current_dps: dps, newval: procedures };
    const result = await run(config.arrows.length ? 'parameter_page' : 'page_command', inputs);
    if (rule && result && result.projected_numeric !== null) {
      setDrafts((prev) => ({ ...prev, [`${pageKey}:${rule.numeric_field}`]: String(result.projected_numeric) }));
    }
  };
  return <div className="elyse-model-controls">
    <p className="elyse-replay-note">Brouillons de rejeu, pas mesures. Boutons = prévisualisation Python ; aucune transmission.</p>
    <div className="elyse-draft-grid">{groups.map((name) => <div className="elyse-stepper" key={name}>
      <label className="elyse-stepper__label" htmlFor={`${pageKey}-${name}`}>{name}</label>
      <input id={`${pageKey}-${name}`} type="number" step="any" value={drafts[`${pageKey}:${name}`] ?? ''}
        placeholder="Brouillon" disabled={pending}
        onChange={(e) => setDrafts((prev) => ({ ...prev, [`${pageKey}:${name}`]: e.target.value }))} />
      <div className="elyse-stepper__buttons">{config.arrows.filter((r) => r.numeric_field === name).map((rule) =>
        <button type="button" className="elyse-hardware-button" key={rule.arrow} disabled={pending}
          title={`${rule.arrow} : Δ ${rule.delta} (modèle historique, pas limite de sécurité)`}
          onClick={() => context.attempt(() => submit(rule))}>{rule.arrow}</button>)}</div>
    </div>)}</div>
    <div className="elyse-button-row wrap">{config.procedures.map((procedure) =>
      <button type="button" className="elyse-hardware-button" key={procedure} disabled={pending}
        onClick={() => context.attempt(() => submit(null, procedure))}>{procedure}</button>)}</div>
  </div>;
}

function FrequencyEditor({ context }) {
  const [draft, setDraft] = useState('');
  return <form className="elyse-frequency-editor" onSubmit={(e) => {
    e.preventDefault();
    context.attempt(async () => {
      if (!/^-?\d+$/.test(draft) || !Number.isSafeInteger(Number(draft))) {
        throw new Error('Sélecteur entier explicite requis ; plage matérielle non qualifiée.');
      }
      await context.run('machine_frequency', { new_value: Number(draft) });
    });
  }}><label>Fréquence machine · sélecteur historique<input type="number" step="1" value={draft}
      placeholder="Brouillon entier" onChange={(e) => setDraft(e.target.value)} disabled={context.pending} /></label>
    <button type="submit" className="elyse-hardware-button" disabled={context.pending || !context.snapshot}>Prévisualiser fréquence</button>
    <small>Unité et limites non qualifiées. Le modèle remplace aussi le numéro de sélection par 4.</small>
  </form>;
}
function SynchronizationPanel({ context }) {
  const cards = [['Acquisition', ['NI6071E', 'WCM', 'Modulateur', 'HF', 'Faraday']],
    ['Supervision', ['LASER/HF', 'IMAC', 'LASER', 'Oscilloscope 1', 'Oscilloscope 2', 'Machine']]];
  return <div className="elyse-sync-stack"><FrequencyEditor context={context} />
    <div className="elyse-sync-grid">{cards.map(([pc, names]) =>
      <Panel key={pc} title={`Synchronisation carte NI6602 PC ${pc}`}><div className="elyse-readout-grid">
        {names.flatMap((name) => ['Délais', 'Largeur'].map((kind) =>
          <Readout key={`${kind}-${name}`} label={`${kind} ${name}`} unit="µs" />))}
      </div></Panel>)}</div></div>;
}

function PowerSuppliesPanel({ context }) {
  const [values, setValues] = useState({});
  const registry = context.snapshot?.registry;
  return <div className="elyse-power-layout"><Panel title="Alimentations aimants · propriétaire unique">
    <p className="elyse-replay-note">Consignes de rejeu en A. Routage candidat ; limites non vérifiées ; aucun repli DAQmx.</p>
    <div className="elyse-magnet-table" role="table" aria-label="Alimentations aimants">
      <div className="elyse-magnet-table__head" role="row"><span>Élément</span><span>Lecture</span><span>Brouillon A</span><span>Propriétaire</span></div>
      {(registry?.entries || []).map((entry) => <div className="elyse-magnet-table__row" role="row" key={entry.equipment_id}>
        <strong title={entry.crosswalk_status}>{entry.label}</strong><span>—</span>
        <input type="number" step="any" aria-label={`Brouillon ${entry.label}`} value={values[entry.equipment_id] ?? ''}
          placeholder="—" disabled={context.pending} onChange={(e) => setValues({ ...values, [entry.equipment_id]: e.target.value })} />
        <span title={JSON.stringify(entry.route)}>{entry.owner === 'DEVICE_SERVER' ? 'Device Server' : entry.owner === 'LEGACY_ACQ' ? 'Acquisition' : 'À qualifier'}</span>
      </div>)}
    </div><button type="button" className="elyse-hardware-button" disabled={context.pending || !registry}
      onClick={() => context.attempt(async () => {
        const requests = Object.entries(values).filter(([, value]) => value.trim()).map(([equipment_id, value]) =>
          ({ equipment_id, current_a: finiteDraft(value) }));
        if (!requests.length) throw new Error('Saisir au moins une consigne de rejeu.');
        await context.run('magnet_currents', {
          expected_revision: registry.registry_revision, requests, idempotency_key: 'web-replay',
        });
      })}>Prévisualiser consignes aimants</button>
  </Panel><Panel title="Commande groupée"><ModelControls config={context.snapshot?.pages.alimentations} context={context} pageKey="alimentations" /></Panel></div>;
}

function Replayer({ operation, context, help }) {
  const [text, setText] = useState('{}');
  return <form className="elyse-replayer" onSubmit={(e) => {
    e.preventDefault(); context.attempt(() => context.run(operation, JSON.parse(text)));
  }}><p className="elyse-replay-note">{help} Données fournies uniquement ; jamais télémétrie en direct.</p>
    <label>Entrées JSON · {operation}<textarea value={text} spellCheck="false" disabled={context.pending}
      onChange={(e) => setText(e.target.value)} /></label>
    <button type="submit" className="elyse-hardware-button" disabled={context.pending || !context.snapshot}>Rejouer {operation}</button>
  </form>;
}

function i32Draft(value) {
  if (!/^-?\d+$/.test(value) || !Number.isInteger(Number(value)) || Number(value) < -(2 ** 31) || Number(value) > 2 ** 31 - 1) {
    throw new Error('Entier I32 explicite requis pour le scénario.');
  }
  return Number(value);
}

function VideoPanel({ context }) {
  const [section, setSection] = useState('Outils');
  const [status, setStatus] = useState('');
  const [code, setCode] = useState('');
  const [source, setSource] = useState('');
  const [formatted, setFormatted] = useState('');
  const [year, setYear] = useState('');
  const [dialog, setDialog] = useState('pending');
  const [path, setPath] = useState('');
  const [toolPlan, setToolPlan] = useState(null);
  const disabled = context.pending || !context.snapshot;
  const errorScenario = () => {
    if (!['false', 'true'].includes(status)) throw new Error('Choisir explicitement le scénario erreur ; aucun succès pilote supposé.');
    return { status: status === 'true', code: i32Draft(code), source };
  };
  const toolFields = context.snapshot?.video_controls?.tool_fields || [];
  return <div className="elyse-video-layout"><Panel title="Caméra ELYSE — Centroïde" className="elyse-camera-panel">
    <div className="elyse-camera-frame"><span>IMAGE NI1409 INDISPONIBLE</span><small>Aucun flux image connecté</small></div>
    <div className="elyse-readout-grid"><Readout label="Centroïde X" unit="px" /><Readout label="Centroïde Y" unit="px" />
      <Readout label="Seuil NOIR" unit="V" /><Readout label="Seuil BLANC" unit="V" /><Readout label="Voies NI1409" /></div>
    <p className="elyse-video-plan-note">Intentions UI uniquement · NOT_EXECUTED</p>
    {toolPlan?.branch_properties.filter((patch) => patch.control === 'SOURCE' && patch.property !== 'Y Zoom').map((patch, index) =>
      <div className="elyse-video-plan-note" key={index}>{patch.control} · {patch.property} = {JSON.stringify(patch.value?.global_rectangle || patch.value)}</div>)}
  </Panel><Panel title="Réglages vidéo · prévisualisation Python">
    <div className="elyse-subtabs" role="tablist" aria-label="Rejeu vidéo">{['Outils', 'NI1409', 'TIFF'].map((name) =>
      <button type="button" role="tab" aria-selected={section === name} className={section === name ? 'is-active' : ''}
        onClick={() => setSection(name)} key={name}>{name}</button>)}</div>
    {section !== 'TIFF' ? <><fieldset className="elyse-video-scenario" disabled={disabled}>
      <legend>Erreur externe · scénario fourni, pas état caméra</legend>
      <label>Statut erreur<select aria-label="Scénario erreur caméra" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">Choisir un scénario</option><option value="false">false · sans erreur (hypothèse)</option><option value="true">true · erreur (hypothèse)</option>
      </select></label><label>Code I32<input aria-label="Code erreur caméra" type="number" step="1" value={code} placeholder="Code explicite"
        onChange={(e) => setCode(e.target.value)} /></label>
      <label className="elyse-video-wide">Source externe<input aria-label="Source erreur caméra" value={source} onChange={(e) => setSource(e.target.value)} /></label>
      {section === 'NI1409' && <label className="elyse-video-wide">Texte formaté externe (facultatif)<input aria-label="Texte formaté caméra" value={formatted}
        onChange={(e) => setFormatted(e.target.value)} /></label>}
    </fieldset>
      {section === 'Outils' ? <div className="elyse-video-tools">{toolFields.map((name, index) =>
        <button type="button" className="elyse-hardware-button" key={name} disabled={disabled} onClick={() => context.attempt(async () => {
          setToolPlan(null);
          const result = await context.run('video_tools', { values: toolFields.map((_, i) => i === index), final_property_error: errorScenario() });
          if (result) setToolPlan(result);
        })}>{name}</button>)}</div>
        : <><p className="elyse-replay-note">Seuils et voie : lectures locales LabVIEW non résolues, pas NewVal du navigateur. Pas de réinitialisation IMAQ réelle.</p>
          <div className="elyse-button-row wrap">{[['camera_thresholds', 'Prévisualiser séquence seuils'], ['camera_channel', 'Prévisualiser séquence voie']].map(([operation, label]) =>
            <button type="button" className="elyse-hardware-button" disabled={disabled} key={operation} onClick={() => context.attempt(() => context.run(operation,
              { final_error: errorScenario(), formatted_text: formatted || null }))}>{label}</button>)}</div></>}
    </> : <><p className="elyse-replay-note">SAVE IMG : plan de dialogue et TIFF ; aucun dialogue système ni fichier écrit.</p>
      <fieldset className="elyse-video-scenario" disabled={disabled}><legend>Résultats externes · scénario TIFF</legend>
        <label>Année décodée<input aria-label="Année décodée TIFF" type="number" step="1" value={year} placeholder="Année explicite" onChange={(e) => setYear(e.target.value)} /></label>
        <label>Résultat dialogue<select aria-label="Scénario dialogue TIFF" value={dialog} onChange={(e) => setDialog(e.target.value)}>
          <option value="pending">En attente</option><option value="cancelled">Annulé</option><option value="selected">Chemin fourni</option></select></label>
        <label className="elyse-video-wide">Chemin opaque<input aria-label="Chemin TIFF fourni" value={path} disabled={disabled || dialog !== 'selected'}
          placeholder="Pas une destination réelle" onChange={(e) => setPath(e.target.value)} /></label></fieldset>
      <button type="button" className="elyse-hardware-button" disabled={disabled} onClick={() => context.attempt(() => context.run('save_image', {
        new_value: true, resolved_year: i32Draft(year), dialog_cancelled: dialog === 'pending' ? null : dialog === 'cancelled',
        selected_path: dialog === 'selected' ? path : null,
      }))}>Prévisualiser TIFF</button></>}
    <div className="elyse-button-row wrap elyse-video-footer"><button type="button" className="elyse-hardware-button" disabled={disabled}
      onClick={() => context.attempt(() => context.run('video_density', {}))}>Vérifier branche densité</button>
      <HardwareButton>RESET</HardwareButton><HardwareButton>SAVE IMG</HardwareButton></div>
  </Panel></div>;
}

function PrimaryPanel({ tab, context }) {
  const snapshot = context.snapshot;
  if (tab === 'voie-directe' || tab === 'voie-deviee') return <BeamLinePanel line={tab === 'voie-directe' ? 'direct' : 'deviated'} />;
  if (tab === 'synoptique') return <SynopticPanel />;
  if (tab === 'newfocus') return <NewFocusPanel />;
  if (tab === 'camera') return <EthernetCameraPanel />;
  if (tab === 'synchro') return <SynchronizationPanel context={context} />;
  if (tab === 'alimentations') return <PowerSuppliesPanel context={context} />;
  if (['fluides', 'ht', 'hf', 'modulateur'].includes(tab)) {
    const key = tab === 'modulateur' ? 'modulator' : tab;
    return <div className="elyse-two-column"><Panel title={tab === 'modulateur' ? 'Commande MODULATEUR' : `Commande ${tab.toUpperCase()}`}>
      <ModelControls config={snapshot?.pages[key]} pageKey={key} context={context} />
    </Panel><Panel title="Lecture Acquisition · indisponible"><Flags names={snapshot?.display_fields[key]} />
      {tab === 'hf' && ['Puissance incidente', 'Puissance réfléchie', 'Phase mesurée'].map((label) => <Readout label={label} key={label} />)}
      {tab === 'fluides' && ['T° CANON', 'T° SECTION'].map((label) => <Readout label={label} unit="°C" key={label} />)}
      {tab === 'ht' && <p>État alimentation HT inconnu — aucune mesure connectée</p>}
    </Panel></div>;
  }
  if (tab === 'radioprotection') return <div className="elyse-two-column"><Panel title="Radioprotection · états inconnus">
    <Flags names={snapshot?.display_fields.radioprotection} /></Panel><Panel title="Projection des entrées Acquisition">
    <Replayer key="display_flags" operation="display_flags" context={context}
      help="c3 : 56 booléens ; c4 : 64 booléens ; eps : 77 booléens. Polarité non qualifiée ; indicateurs ≠ interlocks." /></Panel></div>;
  return <VideoPanel context={context} />;
}

function Coverage({ snapshot }) {
  if (!snapshot) return <div className="elyse-empty-view">Rapport indisponible</div>;
  return <div className="elyse-coverage"><strong>{snapshot.coverage.bounded_event_indices}/34 événements : modèles bornés · 0 VI complètement qualifié</strong>
    <p>Copie principale {snapshot.source_integrity.matches ? 'conforme' : 'différente de la source analysée'}. Error Code Database.vi exclu.</p>
    {snapshot.coverage.events.map((event) => <details key={event.event_index}><summary>{event.event_index} · {event.label}</summary><p>{event.boundary}</p></details>)}
  </div>;
}
function effectLabel(effect) {
  const args = Object.fromEntries(effect.arguments || []);
  if (effect.operation === 'Wait (ms)' && args.ms != null) return `Wait ${args.ms} ms (intention)`;
  if (effect.operation === 'Read from Text File' && args.count != null) return `${effect.operation} · count=${args.count} · résultat non consommé`;
  return effect.operation;
}
function BottomWorkspace({ context }) {
  const [lower, setLower] = useState('Vide Graphique');
  const [diag, setDiag] = useState('Profils XY');
  const tabs = (names, selected, choose, label) => <div className="elyse-subtabs" role="tablist" aria-label={label}>
    {names.map((name) => <button type="button" role="tab" aria-selected={selected === name} className={selected === name ? 'is-active' : ''}
      onClick={() => choose(name)} key={name}>{name}</button>)}</div>;
  return <div className="elyse-bottom-workspace"><Panel title="Vide et journal" className="elyse-bottom-panel">
    {tabs(['Vide Graphique', 'Fichiers', 'Messages', 'Rapport', 'Vidéo'], lower, setLower, 'Vide et fichiers')}
    <div className="elyse-bottom-content">{lower === 'Rapport' ? <Coverage snapshot={context.snapshot} />
      : lower === 'Messages' ? <div className="elyse-replay-history">{context.history.length ? context.history.map((item, index) =>
        <div key={index}>{item.operation} · NOT_EXECUTED</div>) : 'Messages · aucune donnée connectée'}</div>
        : lower === 'Fichiers' ? <Replayer key="journal" operation="journal" context={context}
          help="message_input, journal_in, display_timestamp, file_timestamp : octets base64 ; file_path_token : texte ou null. Aucun fichier écrit." />
          : lower === 'Vidéo' ? <ElyseMotion context={context} />
          : <Trend label={`${lower} · télémétrie indisponible`} />}</div>
  </Panel><Panel title="Diagnostics faisceau" className="elyse-bottom-panel">
    {tabs(['Centroïde', 'Profils XY', 'Diag', 'Beam profile'], diag, setDiag, 'Diagnostics faisceau')}
    <div className="elyse-bottom-content">{diag === 'Profils XY'
      ? <div className="elyse-profile-pair"><Trend label="Profil X · aucune mesure" /><Trend label="Profil Y · aucune mesure" /></div>
      : diag === 'Beam profile' ? <Replayer key="profiles" operation="profiles" context={context}
        help="iteration, average_count, buffers {x, y}, x_samples, y_samples : tableaux numériques explicites. Seuil intégral natif : > 1000." />
        : diag === 'Diag' ? <ElyseBeamline context={context} synchronization={<Replayer key="synchronisation" operation="synchronisation" context={context}
          help="current_dps : 29 champs nommés ; oldval/newval : 33 DBL dans l’ordre natif ; stored_flash_index explicite (ou null si changement)." />} />
          : diag === 'Centroïde' ? <div className="elyse-centroid-replay"><Readout label="Centroïde X" /><Readout label="Centroïde Y" />
            <button type="button" className="elyse-hardware-button" disabled={context.pending || !context.snapshot?.beamline_controls}
              onClick={() => context.attempt(() => context.run('centroid_reset', {}))}>Prévisualiser RESET moy CxCy</button>
            <p>Plan True → 200 ms → False. Aucun buffer réinitialisé ; observation par la boucle consommatrice non prouvée.</p></div>
          : <Trend label={`${diag} · aperçu en attente de télémétrie`} />}</div>
  </Panel></div>;
}

export default function Elyse({ client = elyseSupervisionClient }) {
  const [activeTab, setActiveTab] = useState(() => {
    if (client !== elyseSupervisionClient) return 'synchro';
    try {
      const saved = window.localStorage.getItem('elyse.supervision.tab');
      return TABS.some(([id]) => id === saved) ? saved : 'synchro';
    } catch (error) { return 'synchro'; }
  });
  const [snapshot, setSnapshot] = useState(null);
  const [businessAcq, setBusinessAcq] = useState(null);
  const [message, setMessage] = useState('Chargement des modèles Python · aucune commande matérielle');
  const [dps, setDps] = useState({});
  const [drafts, setDrafts] = useState({});
  const [pending, setPending] = useState(false);
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState([]);
  const liveAvailable = typeof client.telemetry === 'function';
  const [telemetryRevision, setTelemetryRevision] = useState(0);
  const telemetry = useAcquisitionTelemetry(client, liveAvailable && activeTab !== 'acq-runtime', telemetryRevision);
  const controller = useRef(null);
  const busy = useRef(false);
  const consoleRef = useRef(null);
  useEffect(() => {
    // UI preference only. Never restores authority, DPS or commands from cache.
    if (client === elyseSupervisionClient) {
      try { window.localStorage.setItem('elyse.supervision.tab', activeTab); } catch (error) { /* Optional storage. */ }
    }
  }, [activeTab, client]);
  useEffect(() => {
    const root = consoleRef.current;
    const fit = () => root.style.setProperty('--elyse-top', `${root.getBoundingClientRect().top}px`);
    fit();
    window.addEventListener('resize', fit);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(fit);
    if (root.previousElementSibling) observer?.observe(root.previousElementSibling);
    return () => { window.removeEventListener('resize', fit); observer?.disconnect(); };
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    client.snapshot(abort.signal).then((data) => {
      if (abort.signal.aborted) return;
      setSnapshot(data); setDps(Object.fromEntries(data.dps_fields.map((name) => [name, false])));
      setMessage('MODÈLES PYTHON · REJEU UNIQUEMENT · AUCUNE COMMANDE TRANSMISE');
    }).catch((error) => { if (!abort.signal.aborted) setMessage(`Backend indisponible · ${error.message}`); });
    return () => { abort.abort(); controller.current?.abort(); };
  }, [client]);
  const attempt = async (callback) => {
    setPreview(null);
    try { await callback(); } catch (error) { if (error.name !== 'AbortError') setMessage(`Rejeu refusé · ${error.message}`); }
  };
  const run = async (operation, inputs) => {
    if (!snapshot) throw new Error('Modèles Python indisponibles.');
    if (busy.current) throw new Error('Un rejeu est déjà en cours.');
    busy.current = true; setPending(true); setPreview(null);
    const abort = new AbortController(); controller.current = abort;
    try {
      const data = await client.replay(operation, inputs, abort.signal);
      if (abort.signal.aborted) return null;
      setPreview(data); setHistory((prev) => [data, ...prev].slice(0, 20));
      setMessage(`${operation} · calcul Python terminé · NOT_EXECUTED`);
      return data.result;
    } finally { busy.current = false; if (!abort.signal.aborted) setPending(false); }
  };
  const context = { snapshot, dps, drafts, setDrafts, pending, run, attempt, history };
  const businessView = activeTab === 'business';
  const telemetryView = activeTab === 'telemetry';
  const runtimeView = activeTab === 'acq-runtime';
  const readOnlyView = telemetryView || runtimeView;
  const liveView = !businessView && !readOnlyView && liveAvailable;
  const simulatedConnection = businessView && businessAcq?.mode === 'SIMULATION'
    && businessAcq?.quality === 'SIMULATED';
  return <div className="elyse-console elyse-console--extended" ref={consoleRef}><header className={`elyse-console__header${liveAvailable ? ' elyse-console__header--live' : ''}`}>
    <div className="elyse-brand"><span className="elyse-brand__mark">E</span><div><strong>ELYSE</strong><small>SuperVision Web</small></div></div>
    {!runtimeView && <AcquisitionWatchdog telemetry={telemetry} />}
    {!liveAvailable && !runtimeView && <div className="elyse-mode-banner" role="status" aria-label="État du rejeu SuperVision">{businessView
      ? `${simulatedConnection ? 'ACQ SIMULÉE CONNECTÉE' : 'ACQ NON QUALIFIÉE'} · INTENTIONS ET JOURNAL · AUCUNE TRANSMISSION MATÉRIELLE`
      : telemetryView || liveView ? 'TÉLÉMÉTRIE XP → EVEREST · LECTURE SEULE · AUCUNE COMMANDE' : message}
      </div>}
    {!runtimeView && <MachineFrequency telemetry={telemetry} />}
  </header><div className={`elyse-console__layout${readOnlyView ? ' elyse-console__layout--telemetry' : ''}${liveView ? ' elyse-console__layout--live' : ''}`}>
    <main className={`elyse-workspace${businessView ? ' elyse-workspace--business' : ''}${readOnlyView ? ' elyse-workspace--telemetry' : ''}${liveView ? ' elyse-workspace--live' : ''}`}><nav className="elyse-primary-tabs" role="tablist" aria-label="Pages SuperVision">
      {TABS.map(([id, label]) => <button type="button" role="tab" aria-selected={activeTab === id}
        className={`${activeTab === id ? 'is-active' : ''}${id === 'business' ? ' elyse-business-tab' : ''}${id === 'telemetry' ? ' elyse-telemetry-tab' : ''}`}
        onClick={() => setActiveTab(id)} key={id}><Lamp /><span>{label}</span></button>)}
    </nav><section className="elyse-primary-view" role="tabpanel" aria-label={TABS.find(([id]) => id === activeTab)[1]}>
      {runtimeView ? <AcqRuntime /> : telemetryView ? <AcqTelemetry client={client} telemetry={liveAvailable ? telemetry : undefined}
        onRefresh={liveAvailable ? () => setTelemetryRevision((value) => value + 1) : undefined} />
        : businessView ? <ElyseSupervisionBusiness client={client} onStatus={setBusinessAcq} />
        : liveView ? <LiveSupervision tab={activeTab} client={client} telemetry={telemetry} /> : <PrimaryPanel tab={activeTab} context={context} />}
    </section>{!businessView && !readOnlyView && !liveView && <BottomWorkspace context={context} />}</main>
    {!readOnlyView && !liveView && <aside className="elyse-corrector-rail" aria-label="Réglages rapides ELYSE"><div className="elyse-rail-heading">RÉGLAGES ELYSE</div>
      <div className="elyse-quick-links">
        <button type="button" onClick={() => setActiveTab('hf')}>Phase HF / Laser <span>—</span></button>
        {['H1', 'V1', 'H2', 'V2'].map((name) => <button type="button" key={name}
          onClick={() => setActiveTab('alimentations')} title="Ouvrir la consigne de rejeu ; aucune transmission">
          Correcteur {name} <span>— A</span></button>)}
      </div>
      <details className="elyse-dps-editor"><summary>DPS · scénario fourni</summary>
        <p>Banque hypothétique, pas état du serveur. Initialisation explicite : 29 false.</p>
        {Object.entries(dps).map(([name, value]) => <label key={name}><input type="checkbox" checked={value} disabled={pending}
          onChange={(e) => setDps((prev) => ({ ...prev, [name]: e.target.checked }))} />{name}</label>)}
      </details><div className="elyse-replay-result" aria-label="Résultat du calcul Python">
        {preview ? <><strong>NOT_EXECUTED</strong><span>{preview.result.branch || preview.result.state || preview.operation}</span>
          {preview.result.updated_cluster?.replacements.map(([name, value]) => <div key={name}>{name} = {value}</div>)}
          {preview.result.projected_numeric != null && <div>Brouillon calculé = {preview.result.projected_numeric}</div>}
          {preview.result.acquisition_preview && <div>Acquisition (rejeu) : {preview.result.acquisition_preview.procedure || preview.result.acquisition_preview.state}</div>}
          {preview.result.selected_case != null && <div>Branche vidéo native = {preview.result.selected_case}</div>}
          {preview.result.ter_text && <div>TER (scénario) : {preview.result.ter_text}</div>}
          {preview.operation === 'motor_initialization' && <div>Découverte : {preview.result.discovery_key_supplied ? preview.result.no_devices_message || 'clé fournie, pas pilote validé' : 'inconnue'} · moteurs à zéro (intentions) : {preview.result.zero_motor_numbers.join(', ') || 'aucun'}</div>}
          {preview.result.signed_steps != null && <div>{preview.result.control_label} : moteur symbolique {preview.result.motor_number} ; pas signés = {preview.result.signed_steps} · aucune position physique</div>}
          {preview.result.motion_call && <div>{effectLabel(preview.result.motion_call)} · intention bloquée ; aucun timeout natif</div>}
          {preview.result.polling_calls?.map((effect, i) => <div key={`poll-${i}`}>{effect.operation} · résultat externe non résolu</div>)}
          {preview.operation === 'motor_jog_poll' && <div>Sortie polling (scénario) = {String(preview.result.terminate)} ; GetPosition = {preview.result.motor_position} · pas une mesure</div>}
          {preview.result.abort_intent && <div>AbortMotion.vi · intention bloquée après GetPosition</div>}
          {preview.operation === 'motor_error' && <div>Journal : {preview.result.journal_intent ? JSON.stringify(Object.fromEntries(preview.result.journal_intent.arguments).text) : 'aucune erreur dans le scénario'} · aucun fichier écrit</div>}
          {preview.operation === 'autotune_iteration' && <>
            <div>Centroïde dans [249,251] = {String(preview.result.in_band)} ; sortie boucle interne = {String(preview.result.terminate_inner_loop)}</div>
            <div>Wait {preview.result.wait_ms} ms (intention) ; fraîcheur non prouvée ; itérations non bornées.</div>
            <div>{preview.result.move_intent ? `GoTo (intention) · pas=${Object.fromEntries(preview.result.move_intent.arguments)['Relative Steps']} · connecteur True=${Object.fromEntries(preview.result.move_intent.arguments).true_connector_index} · direction non déduite` : 'Aucune intention GoTo dans cette bande'}</div>
            <small>stop/erreur ne constitue pas une garde avant GoTo.</small>
          </>}
          {preview.operation === 'autotune_outer' && <div>Sortie boucle externe = {String(preview.result.terminate_outer_loop)} · Y seulement ; ignore X et erreur moteur ; pas de preuve d’alignement</div>}
          {preview.result.stage_order && <div>Ordre natif : {preview.result.stage_order.join(' → ')} · runtime non complet</div>}
          {preview.result.completion_journal && <div>« Autotune terminé » : intention sans garde de réussite ; aucun journal écrit</div>}
          {preview.operation === 'autotune_camera' && <div>Caméra autotune : 8 frames ; erreur sans saut moteur démontré</div>}
          {preview.result.position_hg != null && <div>Fentes (valeurs natives) : HG = {preview.result.position_hg} ; HD = {preview.result.position_hd}</div>}
          {preview.result.legacy_command_value != null && <div>{preview.result.station} : commande native = {preview.result.legacy_command_value} ; affichage = {preview.result.display_value} · unités non qualifiées</div>}
          {preview.result.projection_origin && <div>C5 : {preview.result.projection_origin} · fraîcheur non vérifiée</div>}
          {preview.operation === 'translator_selection' && <div>Sélection : pas de commande de position ; autres caméras inchangées. Patches seulement.</div>}
          {preview.result.assignments?.map(([name, value]) => <div key={name}>{name} = {String(value)}</div>)}
          {preview.operation === 'translator_stop' && <div>Arrêt : graphe statique UNMAPPED ; aucun état sûr établi.</div>}
          {preview.result.expression_value != null && <div>Expression brute = {String(preview.result.expression_value)} · terminal NATIVE_UNVERIFIED · pas de décision d’arrêt</div>}
          {preview.operation === 'load_toggle' && <div>LOAD : {preview.result.dialog_required ? 'dialogue prévu' : 'sans dialogue'} · chemin {preview.result.selected_directory == null ? 'non résolu' : JSON.stringify(preview.result.selected_directory)} · aucun fichier lu</div>}
          {preview.operation === 'validate_load' && <div>VALIDER LOAD : sorties des lectures non consommées ; aucune consigne appliquée.</div>}
          {preview.operation === 'tree_selection' && <div>Tag Tree (scénario) = {JSON.stringify(preview.result.current_tag)} · conservé même sur erreur</div>}
          {preview.result.effects?.map((effect, index) => <div key={`effect-${index}`}>{effect.operation} · intention bloquée</div>)}
          {preview.result.ui_patches?.map((patch, index) => <div key={`ui-${index}`}>UI (plan) · {patch.control} = {JSON.stringify(patch.value)}</div>)}
          {preview.result.frames?.length === 0 && <div>Branche vide : aucune écriture.</div>}
          {preview.result.frames?.map((frame) => <div key={frame.index}>Frame {frame.index} : {[
            ...(frame.effects || []).map(effectLabel),
            ...(frame.patches || []).map(([name, value]) => `${name} = ${value}`),
            ...(frame.waits_ms || []).map((ms) => `Wait ${ms} ms (intention)`),
            ...(frame.ui_patches || []).map((patch) => `${patch.control}.${patch.property} = ${JSON.stringify(patch.value)}`),
            ...(frame.shared_variable_write?.assignments || []).map((patch) => `${patch.field} = ${patch.value}`),
            ...(frame.topology || []),
          ].join(' · ') || 'aucun effet'}{frame.operations_within_frame_serialized === false && ' · ordre intra-frame non prouvé'}
            {frame.note && <small>{frame.note}</small>}
            {frame.polling_selector && <small>Expression : {frame.polling_selector.expression} · NATIVE_UNVERIFIED</small>}
            {frame.shared_variable_write?.psp_url === null && <small>Destination PSP non capturée · écriture bloquée</small>}
          </div>)}
          {preview.result.steps?.map((step) => <div key={step.frame_index}>Frame {step.frame_index} : {step.observed_wait_ms != null ? `Wait ${step.observed_wait_ms} ms (intention)` : `${step.target} = ${step.value}`}</div>)}
          {preview.result.final_patches?.map((patch, index) => <div key={index}>Fin · {patch.control} = {String(patch.value)}</div>)}
          {preview.result.selector === false && <div>Densité : branche False constante ; aucun effet atteignable.</div>}
          {preview.result.dialog_pending != null && <div>TIFF : {preview.result.dialog_pending ? 'dialogue en attente' : preview.result.dialog_cancelled ? 'annulé' : 'plan seulement'} · aucun fichier écrit</div>}
          {preview.result.active_guard_fields?.length > 0 && <div>DPS occupé : {preview.result.active_guard_fields.join(', ')}</div>}
          {preview.result.plans?.map((plan) => <div key={plan.equipment_id}>{plan.equipment_id} : {plan.blocked_reasons.join(', ')}</div>)}
          <details><summary>Plan Python complet</summary><pre>{JSON.stringify(preview, null, 2)}</pre></details></>
          : <span>Aucun calcul de rejeu. Aucune commande matérielle.</span>}
      </div>
    </aside>}
  </div><footer className="elyse-console__footer"><span><Lamp /> ACQ : {readOnlyView || liveView ? 'STATUT MATÉRIEL NON ÉTABLI' : simulatedConnection ? 'SIMULÉE CONNECTÉE' : 'DÉCONNECTÉ'}</span>
    <span>SuperVision : {readOnlyView || liveView ? 'LECTURE TÉLÉMÉTRIE' : businessView ? 'INTENTIONS ET JOURNAL' : 'MODÈLES PYTHON'}</span>
    <span>{runtimeView ? 'Entrées Python NI · pas de repli LabVIEW' : telemetryView || liveView ? 'Valeurs LabVIEW · mesures physiques non qualifiées' : 'Télémétrie physique : INDISPONIBLE'}</span><span>Autorité commande : {simulatedConnection ? 'SIMULATION UNIQUEMENT' : 'AUCUNE'}</span></footer></div>;
}
