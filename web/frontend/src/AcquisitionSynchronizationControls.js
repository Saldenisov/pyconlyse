import React, { useState } from 'react';
import { AcquisitionCommand, useAcquisitionConnection } from './AcquisitionCommands';
import HardwareApprovalControl from './components/HardwareApprovalControl';
import { syncTicks, validSyncValue } from './acquisitionCommandValue';

// C10 physical outputs, from the saved ni6602_timing.csv. No invented C11 mapping.
export const SYNC_CHANNELS = [
  'Synchro PCI6071E', 'Synchro variable machine', 'Synchro mesure WCM', 'Synchro modulateur',
  'Synchro HF', 'Synchro cible de Faraday', 'Synchro oscilloscope', 'Gate 1 / 50 Hz — pilote 20 MHz',
];

export default function AcquisitionSynchronizationControls() {
  const [counter, setCounter] = useState(0);
  const [drafts, setDrafts] = useState({});
  const { view, fresh } = useAcquisitionConnection();
  const current = view?.source_selected === true && fresh;
  const state = current ? view?.synchronization : null;
  const running = Array.isArray(state?.running_counters) && state.running_counters.includes(counter);
  const draft = drafts[counter] || { delay: '', width: '' };
  const edit = (key, value) => setDrafts((previous) => ({ ...previous, [counter]: { ...draft, [key]: value } }));
  const value = { counter, delay_us: draft.delay.trim() === '' ? NaN : Number(draft.delay),
    width_us: draft.width.trim() === '' ? NaN : Number(draft.width) };
  const valid = validSyncValue(value);
  const uncertain = Array.isArray(state?.uncertain_counters) && state.uncertain_counters.includes(counter);
  const ticks = !uncertain && state?.commanded_ticks?.[counter];
  const known = ticks && ['initial_delay_ticks', 'low_ticks', 'high_ticks']
    .every((key) => Number.isInteger(ticks[key]) && ticks[key] >= 0);
  return <section aria-label="Synchronisation Acquisition Python">
    <h2>Synchronisation C10 / NI6602</h2>
    <p>Modifier un compteur à la fois. Appliquer arrête puis redémarre uniquement un compteur déjà en marche.
      Les paramètres ne sont pas une mesure physique du signal.</p>
    <HardwareApprovalControl />
    <label htmlFor="acq-sync-counter">Sortie C10</label>
    <select id="acq-sync-counter" value={counter} onChange={(event) => setCounter(Number(event.target.value))}>
      {SYNC_CHANNELS.map((label, index) => <option key={label} value={index}>C10/ctr{index} — {label}</option>)}
    </select>
    <p>{running ? 'Compteur en marche selon le propriétaire NI actuel.' : 'Compteur arrêté ou état indisponible : application désactivée.'}</p>
    <label htmlFor="acq-sync-delay">Délai (µs)</label>
    <input id="acq-sync-delay" type="number" step="any" value={draft.delay}
      onChange={(event) => edit('delay', event.target.value)} />
    <label htmlFor="acq-sync-width">Largeur (µs)</label>
    <input id="acq-sync-width" type="number" step="any" value={draft.width}
      onChange={(event) => edit('width', event.target.value)} />
    {valid && <p>Conversion VI : délai initial = temps bas = {syncTicks(value.delay_us)} ticks ;
      temps haut = {syncTicks(value.width_us)} ticks. Arrondi au pair après multiplication par 20.</p>}
    <AcquisitionCommand operation="counter_timing.set" name="Appliquer synchronisation C10" value={running ? value : null}>
      Appliquer délai et largeur
    </AcquisitionCommand>
    <p aria-label="Dernières propriétés commandées">{known
      ? `Dernières écritures réussies : délai initial ${ticks.initial_delay_ticks}, temps bas ${ticks.low_ticks}, temps haut ${ticks.high_ticks} ticks.`
      : 'Propriétés commandées : indisponibles ou incertaines.'} Aucun readback physique.</p>
    <p>Les compteurs modulateur/HF restent arrêtés avant Marche impulsions modulateur. Leur réglage exige donc cette
      étape préalable ; après modification, une nouvelle Marche impulsions est nécessaire avant une augmentation HT.</p>
    <p>La route VI confirmée ne configure que C10/ctr0–7. Les anciennes rubriques C11/IMAC/détection et une fréquence
      indépendante n’ont pas de commande distante qualifiée et ne sont pas présentées comme réglages actifs.</p>
  </section>;
}
