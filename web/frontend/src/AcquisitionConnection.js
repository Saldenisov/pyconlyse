import React from 'react';
import { useAcquisitionConnection } from './AcquisitionCommands';
import { ACQUISITION_TOPOLOGY } from './api/acqTelemetryClient';

const SOURCE = {
  LABVIEW_BRIDGE: 'VI LabVIEW → relais dans le serveur XP',
  PYTHON_NATIVE: 'NI → acquisition native dans le même serveur XP',
  TRANSITION_OR_FAULT: 'Transition ou défaut · aucune commutation vers un autre serveur',
};

// Display only. Neither a source label nor 27 received banks grants authority.
export default function AcquisitionConnection({ telemetry }) {
  const { view, fresh } = useAcquisitionConnection();
  const sourceMode = fresh ? view?.source_mode : 'UNKNOWN';
  const received = telemetry?.payload?.snapshot;
  const quality = telemetry?.failure ? 'UNAVAILABLE'
    : !received ? 'WAITING' : telemetry.elapsed >= 2 ? 'STALE' : telemetry.payload.quality;
  return <section aria-label="Connexion unique Acquisition" className="acq-command-status">
    <strong>Pyconlyse ↔ Tango ↔ Acquisition</strong>
    <span>Serveur XP unique : {ACQUISITION_TOPOLOGY.xp_host}</span>
    <span>Lecture et commandes : {ACQUISITION_TOPOLOGY.tango_device} · même Device Server Everest</span>
    <span>État logiciel XP : {fresh ? view?.state || 'UNKNOWN' : 'UNAVAILABLE'}</span>
    <span>Source : {SOURCE[sourceMode] || 'Inconnue · attente de métadonnées actuelles'}</span>
    <span>Télémétrie : {quality} · {Object.keys(received?.publications || {}).length} / 27 banques</span>
    <small>Initialize reste local sur XP. Reconnexion des lectures seulement ; aucune remise en marche
      ni répétition de commande automatique. Supervision VI reste transitoire, pas un second propriétaire.</small>
  </section>;
}
