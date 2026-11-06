import React, { useEffect, useState } from 'react';

export const DEFERRED_ACQUISITION_READ = 'VD2 operation in progress; acquisition status not queried';

function updateHistory(current, issues, now) {
  let changed = false;
  const next = current.map(entry => {
    if (entry.resolvedAt || issues[entry.scope]?.message === entry.message) return entry;
    changed = true;
    return { ...entry, resolvedAt: now };
  });
  Object.entries(issues).forEach(([scope, issue]) => {
    if (!issue.message || next.some(entry => entry.scope === scope && !entry.resolvedAt)) return;
    changed = true;
    const id = Math.max(0, ...next.map(entry => entry.id)) + 1;
    next.push({ ...issue, id, scope, observedAt: now, resolvedAt: null });
  });
  return changed ? next.slice(-10) : current;
}

export default function VD2ReadDiagnostics({ issues }) {
  const [history, setHistory] = useState([]);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    const now = Date.now();
    setHistory(current => updateHistory(current, issues, now));
  }, [issues]);
  if (!history.length) return null;
  const latest = history[history.length - 1];
  const activeCount = history.filter(entry => !entry.resolvedAt).length;
  return (
    <details className="vd2-read-history" aria-label="Recent read warnings"
      onToggle={event => setExpanded(event.currentTarget.open)}>
      <summary>Read history ({history.length}) · {new Date(latest.observedAt).toLocaleTimeString()} · {activeCount ? `${activeCount} active` : 'resolved'}</summary>
      {expanded && <><ol reversed>
        {[...history].reverse().map(entry => (
          <li key={entry.id}>
            <div>
              <time dateTime={new Date(entry.observedAt).toISOString()}>{new Date(entry.observedAt).toLocaleTimeString()}</time>
              {' · '}{entry.label}{' · '}
              {entry.resolvedAt ? <>Resolved at <time dateTime={new Date(entry.resolvedAt).toISOString()}>{new Date(entry.resolvedAt).toLocaleTimeString()}</time></> : 'Active'}
            </div>
            <pre>{entry.message}</pre>
          </li>
        ))}
      </ol>
      <button type="button" disabled={!history.some(entry => entry.resolvedAt)}
        onClick={() => setHistory(current => current.filter(entry => !entry.resolvedAt))}>Clear resolved history</button>
      </>}
    </details>
  );
}
