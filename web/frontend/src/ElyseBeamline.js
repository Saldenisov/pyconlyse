import React, { useState } from 'react';

function explicitNumber(value) {
  if (!value.trim() || !Number.isFinite(Number(value))) throw new Error('Valeur numérique explicite requise ; unités et limites non qualifiées.');
  return Number(value);
}
function selector(value) {
  if (!/^-?\d+$/.test(value)) throw new Error('Choisir explicitement le sélecteur historique.');
  return Number(value);
}
function suppliedBoolean(value) {
  if (!['false', 'true'].includes(value)) throw new Error('Choisir explicitement les états EN / NewVal du scénario ; inconnu ≠ false.');
  return value === 'true';
}
function Choice({ label, value, change, options, disabled }) {
  return <label>{label}<select aria-label={label} value={value} onChange={(e) => change(e.target.value)} disabled={disabled}>
    <option value="">Choisir…</option>{options.map((item) => {
      const [key, text] = Array.isArray(item) ? item : [item, String(item)];
      return <option key={key} value={String(key)}>{text}</option>;
    })}</select></label>;
}

export default function ElyseBeamline({ context, synchronization }) {
  const [section, setSection] = useState('Fentes');
  const [axe, setAxe] = useState('');
  const [gap, setGap] = useState('');
  const [supply, setSupply] = useState('');
  const [station, setStation] = useState('');
  const [position, setPosition] = useState('');
  const [mirror, setMirror] = useState('');
  const [faradayMode, setFaradayMode] = useState('position');
  const [faradayStation, setFaradayStation] = useState('');
  const [faradayNewVal, setFaradayNewVal] = useState('');
  const [faradayTab, setFaradayTab] = useState('');
  const [enStates, setEnStates] = useState(['', '', '']);
  const [snapshotText, setSnapshotText] = useState('');
  const [translatorMode, setTranslatorMode] = useState('selection');
  const [translatorSelection, setTranslatorSelection] = useState('');
  const [iteration, setIteration] = useState('');
  const [pollValues, setPollValues] = useState(['', '', '']);
  const meta = context.snapshot?.beamline_controls;
  const translator = context.snapshot?.translator_controls;
  const disabled = context.pending || !meta;
  const frameSnapshots = () => snapshotText.trim() ? JSON.parse(snapshotText) : null;
  const preview = (operation, inputs) => context.attempt(() => context.run(operation, inputs()));
  const button = (label, operation, inputs) => <button type="button" className="elyse-hardware-button" disabled={disabled || (section === 'Translateurs' && !translator)}
    onClick={() => preview(operation, inputs)}>{label}</button>;
  const booleanOptions = [['false', 'false · scénario'], ['true', 'true · scénario']];
  return <div className="elyse-beamline">
    <div className="elyse-subtabs" role="tablist" aria-label="Rejeu ligne faisceau">{['Fentes', 'Faraday', 'T1–T3', 'Miroir', 'Translateurs', 'Synchronisation'].map((name) =>
      <button type="button" role="tab" aria-selected={section === name} className={section === name ? 'is-active' : ''} key={name}
        onClick={() => setSection(name)}>{name}</button>)}</div>
    {section === 'Synchronisation' ? synchronization : <>
      <p className="elyse-replay-note">Scénarios fournis · aucune position mesurée, aucun mouvement. Unités et limites non qualifiées.</p>
      {section === 'Fentes' && <div className="elyse-beamline-grid">
        <label>AXE H · brouillon<input aria-label="AXE H · brouillon" type="number" step="any" value={axe} onChange={(e) => setAxe(e.target.value)} disabled={disabled} /></label>
        <label>GAP H · brouillon<input aria-label="GAP H · brouillon" type="number" step="any" value={gap} onChange={(e) => setGap(e.target.value)} disabled={disabled} /></label>
        {button('Prévisualiser positions fentes', 'slit_position', () => ({ axe_h: explicitNumber(axe), gap_h: explicitNumber(gap) }))}
        <Choice label="Sélecteur alimentation fentes" value={supply} change={setSupply} options={meta?.digital_selectors || []} disabled={disabled} />
        {button('Prévisualiser alimentation fentes', 'slit_supply', () => ({ new_value: selector(supply), frame_snapshots: frameSnapshots() }))}
      </div>}
      {section === 'T1–T3' && <div className="elyse-beamline-grid">
        <Choice label="Station diagnostique" value={station} change={setStation} options={meta?.diagnostic_stations || []} disabled={disabled} />
        <Choice label="Sélecteur position diagnostique" value={position} change={setPosition} options={meta?.diagnostic_selectors || []} disabled={disabled} />
        {button('Prévisualiser position diagnostique', 'diagnostic_position', () => {
          if (!station) throw new Error('Choisir T1, T2 ou T3 ; sens EN/HORS non qualifié.');
          return { station, selector: selector(position) };
        })}
      </div>}
      {section === 'Miroir' && <div className="elyse-beamline-grid">
        <Choice label="Sélecteur miroir LASER" value={mirror} change={setMirror} options={(meta?.digital_selectors || []).map((value) => [value, `${value} · ${value === 0 ? 'EN' : 'HORS'} (nom natif)`])} disabled={disabled} />
        {button('Prévisualiser miroir LASER', 'laser_mirror', () => ({ new_value: selector(mirror), frame_snapshots: frameSnapshots() }))}
      </div>}
      {section === 'Translateurs' && <>
        <Choice label="Modèle Translateurs" value={translatorMode} change={setTranslatorMode}
          options={[['selection', 'Sélection Laser / T1 / T2 / T3'], ['stop', 'Arrêt · graphe statique'], ['expression', 'Expression boucle · un échantillon']]} disabled={disabled || !translator} />
        {translatorMode === 'selection' && <>
          <p>Seuls les champs sélectionnés passent à true. Ne positionne pas les écrans ; ne coupe pas les autres caméras.</p>
          <div className="elyse-beamline-grid">
            <Choice label="Sélection Translateurs" value={translatorSelection} change={setTranslatorSelection}
              options={(translator?.selections || []).map((s) => [s.value, s.label])} disabled={disabled || !translator} />
            {button('Prévisualiser sélection Translateurs', 'translator_selection', () => ({ selection: selector(translatorSelection) }))}
          </div>
        </>}
        {translatorMode === 'stop' && <>
          <p>Arrêt : 4 frames statiques, correspondance visuelle UNMAPPED. Destination WCM5D non capturée ; aucun état sûr établi.</p>
          {button('Inspecter graphe Arrêt Translateurs', 'translator_stop', () => ({}))}
        </>}
        {translatorMode === 'expression' && <>
          <p>Résultat booléen brut ≠ décision d’arrêt. Polarité du terminal inconnue ; aucun timeout garanti.</p>
          <div className="elyse-beamline-grid">
            <label>Itération boucle · scénario<input aria-label="Itération boucle · scénario" type="number" step="1" value={iteration} disabled={disabled || !translator} onChange={(e) => setIteration(e.target.value)} /></label>
            {(translator?.polling_expression.measurement_names || []).map((name, index) => <label key={name}>{name} · scénario
              <input aria-label={`${name} · scénario`} type="number" step="any" value={pollValues[index]} disabled={disabled || !translator}
                onChange={(e) => setPollValues((prev) => prev.map((v, i) => i === index ? e.target.value : v))} /></label>)}
            {button('Évaluer expression Translateurs', 'translator_loop_selector', () => {
              const loopIndex = selector(iteration);
              if (!Number.isSafeInteger(loopIndex)) throw new Error('Indice entier exactement représentable requis pour ce rejeu web.');
              return { iteration: loopIndex, position_miroir_laser: explicitNumber(pollValues[0]), etat_t1: explicitNumber(pollValues[1]), etat_mlaser_en: explicitNumber(pollValues[2]) };
            })}
          </div>
        </>}
      </>}
      {section === 'Faraday' && <>
        <div className="elyse-beamline-grid"><Choice label="Événement Faraday" value={faradayMode} change={setFaradayMode}
          options={[[ 'position', 'Position Faraday · NewVal booléen'], ['tab', 'Onglet Faraday · sélecteur entier']]} disabled={disabled} />
          {faradayMode === 'position' ? <>
            <Choice label="Station Faraday" value={faradayStation} change={setFaradayStation} options={meta?.faraday_stations || []} disabled={disabled} />
            <Choice label="NewVal Position Faraday" value={faradayNewVal} change={setFaradayNewVal} options={booleanOptions} disabled={disabled} />
            {button('Prévisualiser événement Position Faraday', 'faraday_position', () => ({ station: selector(faradayStation), new_value: suppliedBoolean(faradayNewVal), frame_snapshots: frameSnapshots() }))}
          </> : <>
            <Choice label="Sélecteur onglet Faraday" value={faradayTab} change={setFaradayTab} options={(meta?.faraday_tab_selectors || []).map((value) => [value, value === 0 ? '0 · Arrêt (nom natif, pas STOP matériel)' : String(value)])} disabled={disabled} />
            {faradayTab === '0' && (meta?.faraday_en_inputs || []).map((label, index) => <Choice key={label} label={`${label} · scénario`} value={enStates[index]}
              change={(value) => setEnStates((prev) => prev.map((v, i) => i === index ? value : v))} options={booleanOptions} disabled={disabled} />)}
            {button('Prévisualiser onglet Faraday', 'faraday_tab', () => ({ new_value: selector(faradayTab), en_states: faradayTab === '0' ? enStates.map(suppliedBoolean) : null, frame_snapshots: frameSnapshots() }))}
          </>}
        </div>
        <small>NewVal=false et onglets 1/2/3 : branches vides. Arrêt(0) : inversion des EN fournis, pas arrêt de sécurité.</small>
      </>}
      {['Fentes', 'Faraday', 'Miroir'].includes(section) && <details className="elyse-beamline-snapshots"><summary>Snapshots C5 par frame (facultatif)</summary>
        <p>Lecture locale fraîche requise pour chaque écriture. Sans snapshots : patches seulement, pas banque complète. Ne pas réutiliser le premier snapshot après une attente.</p>
        <label>Snapshots C5 JSON<textarea aria-label="Snapshots C5 JSON" value={snapshotText} disabled={disabled} spellCheck="false"
          placeholder='[{"frame_index":0,"cluster":{...}}, ...]' onChange={(e) => setSnapshotText(e.target.value)} /></label>
      </details>}
    </>}
  </div>;
}
