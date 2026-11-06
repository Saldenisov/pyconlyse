import React, { useEffect, useState } from 'react';
import './ErrorJournal.css';

export function journalTimestamp(value) {
  const time = new Date(value);
  return Number.isFinite(time.getTime()) ? time.toLocaleString('fr-FR', {
    timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'shortOffset',
  }) : 'date inconnue';
}

export default function ErrorJournal({ client, children }) {
  const [day, setDay] = useState('');
  const [cursor, setCursor] = useState('');
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState(null);
  const [failure, setFailure] = useState('');
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const abort = new AbortController();
    let timer;
    setData(null); setFailure(''); setLoading(true);
    const read = async () => {
      try {
        if (typeof client.errorJournal !== 'function') throw new Error('Client journal indisponible.');
        const result = await client.errorJournal({ day, cursor }, abort.signal);
        if (!Array.isArray(result.events) || !Array.isArray(result.days)
            || result.storage !== 'server_sqlite') throw new Error('Contrat journal incompatible.');
        if (!abort.signal.aborted) { setData(result); setFailure(''); }
      } catch (error) {
        if (!abort.signal.aborted) setFailure(error.message || 'Journal indisponible.');
      } finally {
        if (!abort.signal.aborted) {
          setLoading(false);
          if (!cursor) timer = setTimeout(read, 5000);
        }
      }
    };
    read();
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => { abort.abort(); clearTimeout(timer); clearInterval(clock); };
  }, [client, day, cursor, revision]);
  const latest = () => { setDay(''); setCursor(''); setRevision((value) => value + 1); };
  return <section className="error-journal" aria-label="Journal des erreurs par jour">
    <h2>Journal des erreurs et alarmes</h2>
    {children}
    <div className="error-journal__tools">
      <button type="button" onClick={latest}>Derniers événements</button>
      <label>Jour · Europe/Paris<input type="date" value={day} list="error-journal-days"
        onChange={(event) => { setDay(event.target.value); setCursor(''); }} /></label>
      <datalist id="error-journal-days">{data?.days.map((item) =>
        <option key={item.day} value={item.day}>{item.count} événements</option>)}</datalist>
      <button type="button" onClick={() => setRevision((value) => value + 1)}>Actualiser</button>
    </div>
    <p>{day || 'Toutes dates · derniers événements'} · du plus récent au plus ancien · heures de Paris.</p>
    {loading && <p role="status">Chargement du journal…</p>}
    {failure && <p role="alert">Lecture du journal impossible : {failure}. Les données affichées ne sont pas actualisées.</p>}
    {data?.journal_error && <p role="alert">ERREUR ARCHIVAGE : {data.journal_error}. Conservation des nouveaux événements non confirmée.</p>}
    {data && <>
      <p>SQLite serveur · dernière lecture : {journalTimestamp(data.observed_utc)}.
        {' '}{data.observer_running ? 'Collecte serveur active.' : 'Collecte continue non confirmée.'}</p>
      <div className="error-journal__sources">{data.sources?.map((item) => {
        const expired = now - Date.parse(item.last_observed_utc) > 10000;
        return <p key={item.stream || item.source}>
          {item.stream || item.source} · {expired ? 'OBSERVATION PÉRIMÉE' : item.quality || 'UNKNOWN'}
          {' · '}{journalTimestamp(item.last_observed_utc)}
          {item.error && ` · ${item.error}`}{item.journal_error && ` · ERREUR JOURNAL SOURCE : ${item.journal_error}`}
          {item.journal_durable === false && ' · journal source non persistant'}
        </p>;
      })}</div>
      <nav className="error-journal__days" aria-label="Jours avec événements">{data.days.map((item) =>
        <button type="button" key={item.day} aria-pressed={day === item.day}
          onClick={() => { setDay(item.day); setCursor(''); }}>{item.day} · {item.count}</button>)}</nav>
      {data.events.length === 0 && <p>Aucun événement enregistré pour cette sélection. Cela ne confirme pas l’absence de défaut matériel.</p>}
      {data.events.length > 0 && <div className="error-journal__scroll"><table>
        <thead><tr><th>Date / heure · Paris</th><th>Source</th><th>Circuit / banque</th><th>Événement</th><th>Détails</th></tr></thead>
        <tbody>{data.events.map((event) => <tr key={event.id}>
          <td><time dateTime={event.observed_utc}>{journalTimestamp(event.observed_utc)}</time></td>
          <td>{event.source}</td><td>{event.circuit || event.details?.bank || 'SYSTÈME'}</td><td>{event.kind}</td>
          <td><details><summary>Données originales</summary><pre>{JSON.stringify(event.details, null, 2)}</pre>
            <p>Reçu le {journalTimestamp(event.recorded_utc)} · {event.category}</p></details></td>
        </tr>)}</tbody>
      </table></div>}
      <div className="error-journal__tools">
        {cursor && <button type="button" onClick={() => setCursor('')}>Première page</button>}
        {data.next_cursor && <button type="button" onClick={() => setCursor(data.next_cursor)}>Événements plus anciens</button>}
      </div>
      <p>{data.note}</p>
    </>}
  </section>;
}
