import React, { useEffect, useMemo, useRef, useState } from 'react';
import useAcquisitionTelemetry from './useAcquisitionTelemetry';
import './AcqTelemetry.css';

const QUALITY = { FRESH: 'Flux récent', STALE: 'Données périmées', WAITING: 'En attente de données',
  READ_ERROR: 'Erreur de lecture LabVIEW', INCOMPLETE: 'Banques manquantes',
  RECEIVER_NOT_READY: 'Récepteur non prêt', UNAVAILABLE: 'Lecture indisponible' };

function valueText(value) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE';
  if (typeof value === 'object') return value.nonfinite || value.integer_decimal || JSON.stringify(value);
  return String(value);
}

export function telemetryRows(data, type, path = '', depth = 0) {
  if (depth > 14) return [{ path, label: 'Structure trop profonde', type: 'inconnue', value: '—' }];
  if (type?.type === 'LvVariant') return telemetryRows(data, type.contained_type, path, depth + 1);
  if (Array.isArray(data) && data.length) {
    return data.flatMap((value, index) => {
      const child = type?.fields?.[index] || type?.elements?.[index] || type?.element_type;
      const childPath = path ? `${path}.${index}` : String(index);
      return telemetryRows(value, child, childPath, depth + 1);
    });
  }
  return [{ path, label: type?.name || (path ? `[${path}]` : 'Valeur'), type: type?.type || 'inconnu',
    value: Array.isArray(data) ? '[]' : valueText(data) }];
}

function bankAge(bank, elapsed) {
  return bank && Number.isFinite(bank.age_seconds) ? bank.age_seconds + elapsed : null;
}

export default function AcqTelemetry({ client, telemetry: sharedTelemetry, onRefresh }) {
  const [selected, setSelected] = useState('C1NI6071E');
  const [search, setSearch] = useState('');
  const [refresh, setRefresh] = useState(0);
  const localTelemetry = useAcquisitionTelemetry(client, sharedTelemetry === undefined, refresh);
  const { payload, failure, elapsed } = sharedTelemetry === undefined ? localTelemetry : sharedTelemetry;
  const [sessionChanged, setSessionChanged] = useState(false);
  const session = useRef(null);
  const previous = useRef({});
  const [changed, setChanged] = useState(new Set());

  useEffect(() => {
    if (payload?.snapshot) {
      const nextSession = payload.snapshot.receiver_session;
      const reset = session.current && session.current !== nextSession;
      if (reset) setSessionChanged(true);
      session.current = nextSession;
      const next = {};
      const differences = new Set();
      Object.entries(payload.snapshot.publications).forEach(([bank, record]) => {
        telemetryRows(record.data, record.lv_type).forEach((row) => {
          const key = `${bank}:${row.path}`;
          next[key] = row.value;
          if (!reset && previous.current[key] !== undefined && previous.current[key] !== row.value) differences.add(key);
        });
      });
      previous.current = next;
      setChanged(differences);
    }
  }, [payload]);

  const snapshot = payload?.snapshot;
  const publications = snapshot?.publications || {};
  const banks = payload?.expected_banks || [];
  const record = publications[selected];
  const age = bankAge(record, elapsed);
  const stale = record && (record.stale || age === null || age >= (payload?.stale_after_seconds || 2));
  const anyStale = Object.values(publications).some((bank) => bank.stale || bankAge(bank, elapsed) >= 2);
  const quality = failure ? 'UNAVAILABLE' : anyStale && payload?.quality === 'FRESH' ? 'STALE' : payload?.quality || 'WAITING';
  const rows = useMemo(() => record ? telemetryRows(record.data, record.lv_type) : [], [record]);
  const filtered = rows.filter((row) => `${row.label} ${row.path} ${row.type} ${row.value}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));

  return <div className="acq-telemetry">
    <div className={`acq-telemetry__status acq-telemetry__status--${quality.toLowerCase()}`} role="status" aria-label="État télémétrie Acquisition">
      <strong>{QUALITY[quality]}</strong><span>10.20.30.10 → Python 3.4 → Everest · lecture seule</span>
      <button type="button" onClick={onRefresh || (() => setRefresh((value) => value + 1))}>Actualiser</button>
    </div>
    {failure && <p className="acq-telemetry__error" role="alert">{failure} {payload && 'Dernier instantané conservé, pas une lecture actuelle.'}</p>}
    {sessionChanged && <p className="acq-telemetry__notice">Session du récepteur modifiée : les anciennes valeurs ne sont pas reprises.</p>}
    <div className="acq-telemetry__metrics">
      <div><span>Récepteur Tango</span><strong>{payload?.server_state || '—'}</strong><small>elyse/acquisition/telemetry</small></div>
      <div><span>Instantanés reçus · session</span><strong>{snapshot?.received_this_process ?? '—'}</strong><small>Doublons : {snapshot?.duplicate_receipts ?? '—'}</small></div>
      <div><span>Banques reçues</span><strong>{Object.keys(publications).length} / 27</strong><small>Erreurs de lecture : {payload?.error_banks?.length ?? '—'}</small></div>
      <div><span>Dernière réception Everest</span><strong className="acq-telemetry__timestamp">{record?.received_utc_on_everest || '—'}</strong><small>Actualisation automatique · 1 s</small></div>
    </div>
    <p className="acq-telemetry__notice">Valeurs des contrôles LabVIEW, non atomiques entre cartes. Mesures physiques et concordance PSP non qualifiées.
      {' '}RAM : dernières valeurs seulement. Aucun historique, SQLite ni commande matérielle.</p>
    <div className="acq-telemetry__content">
      <nav className="acq-telemetry__banks" aria-label="Banques de télémétrie">
        {banks.map((bank) => {
          const item = publications[bank];
          const state = !item ? 'absent' : item.error?.status || item.error?.code ? 'erreur' : item.stale || bankAge(item, elapsed) >= 2 ? 'périmé' : 'récent';
          return <button type="button" key={bank} aria-pressed={selected === bank} onClick={() => setSelected(bank)}>
            <span>{bank}</span><small>{state}</small></button>;
        })}
        {!banks.length && <p>En attente du récepteur…</p>}
      </nav>
      <section className="acq-telemetry__values" aria-label={`Valeurs ${selected}`}>
        <div className="acq-telemetry__bank-heading"><h2>{selected}</h2><span>{!record ? 'ABSENT' : stale || failure ? 'DERNIÈRES VALEURS · PÉRIMÉES' : 'RÉCENT · PAS UNE AUTORISATION MATÉRIELLE'}</span></div>
        <div className="acq-telemetry__bank-meta"><span>Séquence : {record?.sequence ?? '—'}</span>
          <span>Âge réception XP : {age === null ? '—' : `${age.toFixed(1)} s`}</span><span>{rows.length} champs</span></div>
        {record?.error && (record.error.status || record.error.code !== 0) && <p role="alert" className="acq-telemetry__error">Erreur LabVIEW {record.error.code} : {record.error.source}</p>}
        <label className="acq-telemetry__filter">Filtrer les champs<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nom, canal, type ou valeur" /></label>
        {!record ? <p>Aucune valeur reçue pour cette banque.</p> : <div className="acq-telemetry__table-wrap"><table aria-label={`Champs ${selected}`}>
          <thead><tr><th>Index</th><th>Champ LabVIEW</th><th>Type</th><th>Dernière valeur</th></tr></thead>
          <tbody>{filtered.map((row) => <tr key={row.path} className={changed.has(`${selected}:${row.path}`) ? 'acq-telemetry__changed' : ''}>
            <td>{row.path || '0'}</td><th scope="row">{row.label}</th><td>{row.type}</td><td><output>{row.value}</output></td>
          </tr>)}</tbody></table>{!filtered.length && <p>Aucun champ correspondant.</p>}</div>}
      </section>
    </div>
    <small className="acq-telemetry__session">Session récepteur : {snapshot?.receiver_session || '—'} · Changement de valeur : surbrillance bleue. TRUE/FALSE ne signifie pas « sûr ».</small>
  </div>;
}
