import React, { useState } from 'react';
import { AcquisitionCommand } from './AcquisitionCommands';
import HardwareApprovalControl from './components/HardwareApprovalControl';
import './AcquisitionExperimentControls.css';

const STAGES = [
  ['General', 'modulator.general'], ['Chauffage', 'chauffage'], ['PREMA', 'prema'],
  ['Focales', 'focales'], ['Relais HT', 'relays_ht'], ['Alimentation HT', 'alimentation_ht'],
  ['Impulsions modulateur', 'modulator_impulse'],
];

export default function AcquisitionExperimentControls() {
  const [target, setTarget] = useState('');
  const voltage = target.trim() === '' ? null : Number(target);
  return <section className="acq-experiment" aria-label="Commandes Acquisition Python">
    <h2>Commandes Acquisition Python</h2>
    <p>Chaque action est distincte et exige une confirmation. Le serveur décide des autorisations selon les entrées,
      l’état logiciel et les qualifications locales. Aucune étape suivante, relance ou augmentation HT automatique.</p>
    <fieldset>
      <legend>Autorisation matérielle externe à usage unique</legend>
      <p>Coller uniquement un nonce accordé séparément par le mécanisme d’autorisation matérielle.
        Ce panneau ne crée aucune autorisation. L’armement prépare un seul envoi, y compris pour Arrêt General ;
        il ne remplace ni la connexion authentifiée, ni les autorisations du serveur, ni la confirmation.</p>
      <HardwareApprovalControl />
    </fieldset>
    <fieldset>
      <legend>Étapes du modulateur</legend>
      {STAGES.map(([label, operation]) => <div className="acq-experiment__row" key={operation}>
        <span>{label}</span>
        <AcquisitionCommand operation={`${operation}.start`} name={`Marche ${label}`}>Marche</AcquisitionCommand>
        <AcquisitionCommand operation={`${operation}.stop`} name={`Arrêt ${label}`}>Arrêt</AcquisitionCommand>
      </div>)}
    </fieldset>
    <fieldset>
      <legend>Consigne HT explicite</legend>
      <label htmlFor="acq-ht-target">Valeur demandée HT (kV)</label>
      <input id="acq-ht-target" type="number" min="0" max="20" step="any" value={target}
        onChange={(event) => setTarget(event.target.value)} />
      <AcquisitionCommand operation="ht_voltage.set" name="Appliquer consigne HT" value={voltage}>Préparer la consigne</AcquisitionCommand>
      <p>La boîte de confirmation affiche la valeur exacte. Modifier la saisie annule cette autorisation.
        Une commande terminée ne prouve pas la tension mesurée.</p>
    </fieldset>
    <fieldset>
      <legend>Impulsions de source — qualification physique requise</legend>
      <div className="acq-experiment__row">
        <span>Faraday 1</span>
        <AcquisitionCommand operation="faraday_1.en_pulse" name="Faraday 1 — impulsion source EN">Impulsion source EN</AcquisitionCommand>
      </div>
      <div className="acq-experiment__row">
        <span>Faraday 3</span>
        <AcquisitionCommand operation="faraday_3.en_pulse" name="Faraday 3 — impulsion source EN">Impulsion source EN</AcquisitionCommand>
      </div>
      <p>EN désigne le chemin de commande VI, pas une position ouverte ou fermée. L’ambiguïté EN/HORS de Faraday 3
        reste à qualifier physiquement. Aucune commande HORS Faraday n’est proposée.</p>
      <div className="acq-experiment__row">
        <span>Miroir laser</span>
        <AcquisitionCommand operation="laser_mirror.en_pulse" name="Miroir laser — impulsion source EN">Impulsion source EN</AcquisitionCommand>
        <AcquisitionCommand operation="laser_mirror.hors_pulse" name="Miroir laser — impulsion source HORS">Impulsion source HORS</AcquisitionCommand>
      </div>
      <p>Les noms EN/HORS ne confirment aucune position physique ni disponibilité du faisceau.
        Ces commandes restent désactivées sans autorisation qualifiée du serveur.</p>
    </fieldset>
  </section>;
}
