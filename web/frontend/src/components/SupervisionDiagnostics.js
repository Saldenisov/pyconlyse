import React, { useCallback, useEffect, useRef, useState } from 'react';
import AcquisitionVideo from './AcquisitionVideo';
import { supervisionDiagnosticsClient } from '../api/supervisionDiagnosticsClient';
import { acqVideoClient } from '../api/acqVideoClient';
import './SupervisionDiagnostics.css';

// Raw channel is authoritative. Native source-label/value binding is not yet
// qualified; a cached view must never select or relabel a physical input.
export const CAMERA_SOURCES = [
  { channel: 0, label: 'Canal brut 0' }, { channel: 1, label: 'Canal brut 1' },
  { channel: 2, label: 'Canal brut 2' }, { channel: 3, label: 'Canal brut 3' },
];
export const DIAGNOSTIC_TABS = ['Centroïde', 'Profils X Y', 'Diag', 'WCM', 'Beam profile'];
const DIAG_GROUPS = [
  { name: 'Laser / translateurs', tabs: ['Arrêt', 'Laser', 'Translateur1', 'Translateur2', 'Translateur3'] },
  { name: 'Cages de Faraday', tabs: ['Arrêt', 'Cage Faraday1', 'Cage Faraday2', 'Cage Faraday3'] },
  { name: 'Fente', tabs: ['Arrêt', 'Fente'] },
];
const cameraId = (channel) => `ni1409:${channel}`;
const finite = (value) => typeof value === 'number' && Number.isFinite(value);

// Exact front-panel controls from native_saved_main_readback/0_SUP_ELYSE_FPHb.xml.
// These identifiers identify presentation only; they are not motor addresses.
const TRANSLATORS = {
  1: { state: 28498, position: 28485, command: 28471, readback: 28052 },
  2: { state: 25476, position: 29402, command: 33032, readback: 38266 },
  3: { state: 30904, position: 30891, command: 30875, readback: 25389 },
};
const FARADAYS = {
  1: { en: 23358, hors: 34428, position: 23482 },
  2: { en: 24760, hors: 24786, position: 24412 },
  3: { en: 31298, hors: 31311, position: 31046 },
};
function NativeReadout({ label, nativeId, unit = '' }) {
  return <div className="supervision-diagnostics__native-readout" data-native-id={nativeId}>
    <span>{label}</span><output aria-label={label} title="Valeur non publiée">—</output><small>{unit}</small>
  </div>;
}
function NativeState({ label, nativeId }) {
  return <div className="supervision-diagnostics__native-state" data-native-id={nativeId}>
    <span aria-hidden="true" className="supervision-diagnostics__unknown-lamp" />
    <span>{label}</span><output aria-label={label}>Inconnu</output>
  </div>;
}
function NativePosition({ label, nativeId, options }) {
  return <label className="supervision-diagnostics__native-input" data-native-id={nativeId}>
    {label}<select aria-label={label} disabled value="" readOnly>
      <option value="">Non lu</option>{options.map((value) => <option key={value} value={value}>{value}</option>)}
    </select>
  </label>;
}
function NativeNumber({ label, nativeId, unit = '' }) {
  return <label className="supervision-diagnostics__native-input" data-native-id={nativeId}>
    {label}<input aria-label={label} type="number" disabled value="" placeholder="Non lu" readOnly />
    {unit && <small>{unit}</small>}
  </label>;
}
function NativeTranslator({ station }) {
  const ids = TRANSLATORS[station];
  return <div className="supervision-diagnostics__native-grid">
    <NativeState label={`Etat T${station}`} nativeId={ids.state} />
    <NativePosition label={`Position diagnostique T${station}`} nativeId={ids.position}
      options={['Position FAISCEAU', 'Position ECRAN', 'Position CERENKOV']} />
    <NativeNumber label={`Cmd pos T${station}`} nativeId={ids.command} unit="mm natifs" />
    <NativeReadout label={`Lec. pos T${station}`} nativeId={ids.readback} unit="mm natifs" />
  </div>;
}
function NativeFaraday({ station }) {
  const ids = FARADAYS[station];
  return <div className="supervision-diagnostics__native-grid">
    <NativeState label={`Etat Faraday ${station} EN`} nativeId={ids.en} />
    <NativeState label={`Etat Faraday ${station} HORS`} nativeId={ids.hors} />
    <NativePosition label={`Position Faraday ${station}`} nativeId={ids.position} options={['EN', 'HORS']} />
  </div>;
}
function NativeDiagContent({ group, selected }) {
  if (group.name === 'Laser / translateurs') {
    if (selected === 'Laser') return <div className="supervision-diagnostics__native-grid">
      <NativeState label="Etat MLaser EN" nativeId={24747} />
      <NativeState label="Etat MLaser HORS" nativeId={26167} />
      <NativePosition label="Position Miroir Laser" nativeId={24728}
        options={['Position miroir LASER EN', 'Position miroir LASER HORS']} />
    </div>;
    if (selected.startsWith('Translateur')) return <NativeTranslator station={Number(selected.slice(-1))} />;
    return <div className="supervision-diagnostics__native-grid">{[1, 2, 3].map((station) =>
      <React.Fragment key={station}><NativeState label={`Etat T${station}`} nativeId={TRANSLATORS[station].state} />
        <NativeReadout label={`Lec. pos T${station}`} nativeId={TRANSLATORS[station].readback} unit="mm natifs" /></React.Fragment>)}
    </div>;
  }
  if (group.name === 'Cages de Faraday') {
    if (selected !== 'Arrêt') return <NativeFaraday station={Number(selected.slice(-1))} />;
    return <div className="supervision-diagnostics__native-grid">{[1, 2, 3].map((station) =>
      <NativeState key={station} label={`Etat Faraday ${station} EN`} nativeId={FARADAYS[station].en} />)}</div>;
  }
  return <div className="supervision-diagnostics__native-grid">
    {selected === 'Fente' && <><NativeNumber label="AXE H" nativeId={118190} unit="mm natifs" />
      <NativeNumber label="GAP H" nativeId={81237} unit="mm natifs" /></>}
    <NativeReadout label="AXE FENTE H" nativeId={selected === 'Arrêt' ? 70740 : 71883} unit="mm natifs" />
    <NativeReadout label="GAP FENTE H" nativeId={selected === 'Arrêt' ? 17909 : 116684} unit="mm natifs" />
    {selected === 'Fente' && <><NativeReadout label="AXE FENTE V" nativeId={127534} unit="mm natifs" />
      <NativeReadout label="GAP FENTE V" nativeId={138492} unit="mm natifs" /></>}
  </div>;
}

function NativeDiagGroup({ group }) {
  const [selected, setSelected] = useState(group.tabs[0]);
  const key = group.name.replace(/\W+/g, '-');
  return <section className="supervision-diagnostics__actuator" aria-label={group.name}>
    <h3>{group.name}</h3>
    <div role="tablist" aria-label={`Panneaux ${group.name}`}>
      {group.tabs.map((tab) => <button type="button" role="tab" key={tab}
        aria-selected={selected === tab} aria-controls={`${key}-panel`}
        onClick={() => setSelected(tab)}>{tab}</button>)}
    </div>
    <div id={`${key}-panel`} role="tabpanel" aria-label={`${group.name} · ${selected}`}>
      <NativeDiagContent group={group} selected={selected} />
      <small>Lectures non publiées · commandes non raccordées au serveur.
        Les unités natives ne constituent pas une calibration validée.</small>
    </div>
  </section>;
}

function Profile({ values, axis, current }) {
  const valid = current && Array.isArray(values) && values.length > 1 && values.length <= 4096 && values.every(finite);
  const maximum = valid ? Math.max(...values) : 0;
  const points = valid ? values.map((value, index) =>
    `${index * 300 / (values.length - 1)},${110 - (maximum > 0 ? value * 100 / maximum : 0)}`).join(' ') : '';
  return <figure className="supervision-diagnostics__profile">
    <figcaption>Profil {axis} · intensité après soustraction du fond</figcaption>
    <svg viewBox="0 0 310 125" role="img" aria-label={`Profil ${axis}`}>
      <path d="M0 10 V110 H300" className="supervision-diagnostics__axis" />
      {valid && <polyline points={points} />}
    </svg>
    <p>{valid ? `${values.length} pixels · maximum ${maximum.toFixed(1)}` : 'Profil actuel indisponible.'}</p>
  </figure>;
}

function CentreEvolution({ history = [] }) {
  const values = history.flatMap((point) => [point.x, point.y]);
  const low = values.length ? Math.min(...values) : 0;
  const span = values.length ? Math.max(1, Math.max(...values) - low) : 1;
  const points = (axis) => history.map((point, index) =>
    `${index * 300 / Math.max(1, history.length - 1)},${110 - (point[axis] - low) * 100 / span}`).join(' ');
  return <figure className="supervision-diagnostics__profile supervision-diagnostics__evolution">
    <figcaption>Évolution Cx/Cy · observations récentes de cette vue</figcaption>
    <svg viewBox="0 0 310 125" role="img" aria-label="Évolution des centroïdes X et Y">
      <path d="M0 10 V110 H300" className="supervision-diagnostics__axis" />
      {history.length > 1 && <><polyline points={points('x')} /><polyline className="supervision-diagnostics__cy" points={points('y')} /></>}
    </svg>
    <p>{history.length ? `${history.length} observations · Cx cyan · Cy rose` : 'Aucune observation valide.'}</p>
  </figure>;
}

export default function SupervisionDiagnostics({ client = supervisionDiagnosticsClient,
  videoClient = acqVideoClient, enabled = true }) {
  const [tab, setTab] = useState(DIAGNOSTIC_TABS[0]);
  const [channel, setChannel] = useState(2);
  const [secondChannel, setSecondChannel] = useState(1);
  const [dual, setDual] = useState(false);
  const [targetFps, setTargetFps] = useState(25);
  const [rows, setRows] = useState({});
  const [now, setNow] = useState(() => performance.now());
  const [error, setError] = useState('');
  const [mutationError, setMutationError] = useState('');
  const [saving, setSaving] = useState(null);
  const [radiusByCamera, setRadiusByCamera] = useState({});
  const mounted = useRef(false);
  const mutationAbort = useRef(null);
  const mutationPending = useRef(false);

  const merge = useCallback((payload) => {
    if (!Array.isArray(payload?.cameras)) throw new Error('État diagnostic incompatible.');
    setRows((old) => {
      const next = { ...old };
      payload.cameras.forEach((row) => {
        if (row?.camera_id !== cameraId(row?.channel)) return;
        const prior = next[row.camera_id];
        const reference = (prior?.reference?.revision || 0) > (row.reference?.revision || 0)
          ? prior.reference : row.reference;
        const modeNewer = (prior?.mode_revision || 0) > (row.mode_revision || 0);
        const at = performance.now();
        const sameStream = prior && prior.source_session_id === row.source_session_id
          && prior.capture_session_id === row.capture_session_id;
        const olderFrame = prior?.frame_identity && row.frame_identity
          && ((sameStream && row.sequence < prior.sequence)
            || (!sameStream && Date.parse(row.observed_utc) < Date.parse(prior.observed_utc)));
        const sample = olderFrame ? prior : row;
        const current = sample.current && { ...sample.current };
        if (current && prior?.frame_identity && row.frame_identity === prior.frame_identity
          && finite(current.age_seconds) && finite(prior.current?.age_seconds)) {
          current.age_seconds = Math.max(current.age_seconds,
            prior.current.age_seconds + Math.max(0, at - prior._receivedAt) / 1000);
        }
        const history = sameStream ? prior?._history || [] : [];
        const newPoint = !olderFrame && row.frame_identity !== history.at(-1)?.identity
          && current?.valid === true && current.quality === 'CURRENT' && current.age_seconds < 2
          && finite(current.x) && finite(current.y);
        next[row.camera_id] = { ...sample, current, reference,
          _history: newPoint ? [...history, { identity: row.frame_identity, x: current.x, y: current.y }].slice(-128) : history,
          _receivedAt: olderFrame ? prior._receivedAt : at,
          ...(modeNewer ? { mode: prior.mode, mode_revision: prior.mode_revision, planner: prior.planner }
            : { mode: row.mode, mode_revision: row.mode_revision, planner: row.planner }) };
      });
      return next;
    });
  }, []);

  useEffect(() => {
    mounted.current = true;
    if (!enabled) return () => { mounted.current = false; };
    const abort = new AbortController();
    let timer;
    const poll = async () => {
      try {
        const payload = await client.snapshot(abort.signal);
        if (!abort.signal.aborted) { merge(payload); setError(''); }
      } catch (failure) {
        if (!abort.signal.aborted) setError(failure.message || 'Diagnostic indisponible.');
      } finally {
        if (!abort.signal.aborted) timer = setTimeout(poll, 250);
      }
    };
    poll();
    const clock = setInterval(() => setNow(performance.now()), 250);
    return () => {
      mounted.current = false;
      abort.abort(); mutationAbort.current?.abort(); clearTimeout(timer); clearInterval(clock);
    };
  }, [client, enabled, merge]);

  const observe = useCallback(({ payload }) => {
    if (mounted.current && payload?.diagnostics) merge({ cameras: [payload.diagnostics] });
  }, [merge]);

  const mutate = async (id, operation) => {
    if (mutationPending.current) return;
    mutationPending.current = true;
    const abort = new AbortController();
    mutationAbort.current = abort;
    setSaving(id); setMutationError('');
    try {
      const value = await operation(abort.signal);
      if (mounted.current) merge(value);
    } catch (failure) {
      if (mounted.current) setMutationError(failure.message || 'Modification non enregistrée.');
    } finally {
      mutationPending.current = false;
      if (mounted.current) setSaving(null);
    }
  };
  const visibleChannels = dual ? [...new Set([channel, secondChannel])] : [channel];
  const selected = rows[cameraId(channel)];
  const rowAge = finite(selected?.current?.age_seconds)
    ? selected.current.age_seconds + Math.max(0, now - selected._receivedAt) / 1000 : null;
  const profilesCurrent = enabled && ['CURRENT', 'NO_BEAM'].includes(selected?.current?.quality)
    && rowAge !== null && rowAge < 2;
  const cameraSources = [...new Set([...CAMERA_SOURCES.map((source) => source.channel),
    ...Object.values(rows).map((row) => row.channel).filter((value) => Number.isInteger(value)
      && value >= 0 && value <= 0xFFFFFFFF)])].sort((a, b) => a - b)
    .map((value) => ({ channel: value, label: `Canal brut ${value}` }));

  return <section className="supervision-diagnostics" aria-label="Diagnostics SuperVision">
    <header className="supervision-diagnostics__heading"><div>
      <h2>Diagnostics SuperVision</h2>
      <p>Caméras, profils et centrage du faisceau</p>
    </div><div className="supervision-diagnostics__selectors">
      <label>Source affichée<select value={channel} onChange={(event) => setChannel(Number(event.target.value))}>
        {cameraSources.map((source) => <option key={source.channel} value={source.channel}>
          {source.label}</option>)}
      </select></label>
      <label>Cadence d’affichage<select value={targetFps} onChange={(event) => setTargetFps(Number(event.target.value))}>
        <option value={25}>25 images/s</option><option value={12.5}>12,5 images/s</option>
      </select></label>
      <label><input type="checkbox" checked={dual} onChange={(event) => setDual(event.target.checked)} />
        Deux vues indépendantes</label>
      {dual && <label>Deuxième source affichée<select value={secondChannel}
        onChange={(event) => setSecondChannel(Number(event.target.value))}>
        {cameraSources.map((source) => <option key={source.channel} value={source.channel}>{source.label}</option>)}
      </select></label>}
    </div></header>
    <p className="supervision-diagnostics__source-note">La NI1409 acquiert une source sélectionnée à la fois.
      Deux vues conservent leurs propres dernières images et âges. Afficher une vue ne commute pas la carte.
      Sources nommées dans le VI : Translateur1, Translateur2, LASER1, MUX/LASER2.
      Leur correspondance avec les canaux bruts reste à qualifier.</p>
    {error && <p role="alert">{error}</p>}
    {mutationError && <p role="alert">{mutationError}</p>}
    <div className="supervision-diagnostics__layout">
      <div className={`supervision-diagnostics__cameras${dual ? ' supervision-diagnostics__cameras--dual' : ''}`}>
        {visibleChannels.map((sourceChannel) => {
          const id = cameraId(sourceChannel);
          const row = rows[id];
          const source = cameraSources.find((item) => item.channel === sourceChannel);
          const radius = radiusByCamera[id] ?? row?.reference?.radius_px ?? 10;
          return <AcquisitionVideo key={id} channel={sourceChannel} title={`${source.label} · NI1409`}
            client={videoClient} enabled={enabled} targetFps={targetFps} diagnostics={row}
            onObservation={observe} radiusPx={radius} onRadiusChange={(value) =>
              setRadiusByCamera((old) => ({ ...old, [id]: value }))}
            savingReference={saving !== null}
            onSaveReference={(frameRow) => mutate(id, (signal) => client.saveReference({
              camera_id: id, frame_identity: frameRow.frame_identity,
              expected_revision: rows[id]?.reference?.revision || 0, radius_px: Number(radius),
            }, signal))} />;
        })}
      </div>
      <div className="supervision-diagnostics__panels">
        <div role="tablist" aria-label="Onglets diagnostics SuperVision" className="supervision-diagnostics__tabs">
          {DIAGNOSTIC_TABS.map((item) => <button key={item} type="button" role="tab"
            aria-selected={tab === item} aria-controls="supervision-diagnostic-panel"
            onClick={() => setTab(item)}>{item}</button>)}
        </div>
        <div role="tabpanel" id="supervision-diagnostic-panel" aria-label={tab}>
          {tab === 'Centroïde' && <section aria-label="Suivi du centre laser">
            <h3>Centrage · {cameraSources.find((source) => source.channel === channel)?.label}</h3>
            <p>Le centre est calculé dans les pixels bruts. Enregistrer le centre sous l’image conserve cette mesure en base.</p>
            <div className="supervision-diagnostics__mode" role="group" aria-label="Mode de centrage">
              {['manual', 'auto'].map((mode) => <button type="button" key={mode}
                aria-pressed={selected?.mode === mode} disabled={!enabled || !selected || saving !== null}
                onClick={() => mutate(selected.camera_id, (signal) => client.setMode({
                  camera_id: selected.camera_id, mode, expected_revision: selected.mode_revision || 0,
                }, signal))}>{mode === 'manual' ? 'Manuel' : 'Auto'}</button>)}
            </div>
            <p role="status" aria-label="État du centrage automatique">{selected?.planner?.state || 'Indisponible'}
              {' · '}{selected?.planner?.reason || 'Aucune mesure actuelle.'}</p>
            <section aria-label="Commande manuelle picomoteurs"><h4>Picomoteurs</h4>
              <p>{selected?.manual?.reason || 'Route moteur et conversion pixels/pas non raccordées.'}</p>
              <label>Déplacement relatif (pas)<input type="number" disabled value="" placeholder="Non lu" readOnly /></label>
              <div className="supervision-diagnostics__motor-pad">
                {['X avant', 'X arrière', 'Y avant', 'Y arrière', 'Arrêt moteur'].map((label) =>
                  <button key={label} type="button" disabled>{label}</button>)}
              </div>
            </section>
            <p>La préférence Auto peut être enregistrée. Aucun mouvement n’est exécuté tant que la route et la calibration ne sont pas validées.</p>
            {selected?.archive && <small>Archivage des centroïdes : {selected.archive.state || selected.archive.status || 'voir état serveur'}</small>}
            <CentreEvolution history={selected?._history} />
          </section>}
          {tab === 'Profils X Y' && <div className="supervision-diagnostics__profiles">
            <p>Image unique · sans moyenne temporelle. Analyse des pixels affichés, distincte du traitement historique SuperVision.</p>
            <Profile values={selected?.profiles?.x} axis="X" current={profilesCurrent} />
            <Profile values={selected?.profiles?.y} axis="Y" current={profilesCurrent} />
            <fieldset disabled><legend>Réglages vidéo matériels non publiés</legend>
              <label>Seuil NOIR (V)<input value="" placeholder="Non lu" readOnly /></label>
              <label>Seuil BLANC (V)<input value="" placeholder="Non lu" readOnly /></label>
              <button type="button">RESET paramètres caméra</button>
            </fieldset>
          </div>}
          {tab === 'Diag' && DIAG_GROUPS.map((group) => <NativeDiagGroup key={group.name} group={group} />)}
          {tab === 'WCM' && <section><h3>WCM</h3><p>Les mesures WCM qualifiées ne sont pas publiées par ce flux caméra.</p></section>}
          {tab === 'Beam profile' && <section><h3>Beam profile</h3>
            <p>L’analyse d’ovale et la sélection de zone seront ajoutées dans une étape ultérieure.</p>
            <Profile values={selected?.profiles?.x} axis="X" current={profilesCurrent} />
            <Profile values={selected?.profiles?.y} axis="Y" current={profilesCurrent} />
          </section>}
        </div>
      </div>
    </div>
  </section>;
}
