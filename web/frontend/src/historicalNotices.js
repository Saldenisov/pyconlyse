// Display acknowledgments only. Never reset a source journal, command or permit.
import { useCallback, useEffect, useState } from 'react';
import './HistoricalNotices.css';

export const HISTORY_SEEN_KEY = 'elyse-historical-notices-seen-v1';
const CHANGED = 'elyse-historical-notices-changed';
const LIMIT = 256;
const hex = (value) => typeof value === 'string' && /^[0-9a-f]{32}$/.test(value);
const terminal = new Set(['COMPLETED', 'FAILED', 'REJECTED', 'INTERRUPTED']);

export function historicalCommandKey(receipt, currentSession) {
  if (!hex(currentSession) || !hex(receipt?.session_id) || receipt.session_id === currentSession
    || !hex(receipt.command_id) || !terminal.has(receipt.outcome)
    || typeof receipt.operation !== 'string') return null;
  return JSON.stringify(['command-history', receipt.session_id, receipt.command_id,
    receipt.operation, receipt.outcome, receipt.error || '']);
}

export function journalNotice(safety) {
  const history = typeof safety?.journal_history_warning === 'string' ? safety.journal_history_warning : '';
  const error = typeof safety?.journal_error === 'string' ? safety.journal_error : '';
  const storage = typeof safety?.journal_storage_error === 'string' ? safety.journal_storage_error : '';
  const key = history && hex(safety.experiment_session_id) && Number.isSafeInteger(safety.journal_revision)
    && safety.journal_revision >= 0
    // Ordinary journal writes advance journal_revision without creating a new
    // historical writer gap. A new source session or warning must reappear.
    ? JSON.stringify(['journal-history', safety.experiment_session_id, history]) : null;
  return { history, key, currentError: storage || (error !== history ? error : '') };
}

function readSeen() {
  try {
    const raw = window.localStorage.getItem(HISTORY_SEEN_KEY);
    if (!raw) return { keys: [], error: '' };
    const value = JSON.parse(raw);
    if (value?.schema_version !== 1 || !Array.isArray(value.keys) || value.keys.length > LIMIT
      || value.keys.some((key) => typeof key !== 'string' || key.length > 8192)) throw new Error();
    return { keys: value.keys, error: '' };
  } catch (_error) {
    return { keys: [], error: 'Messages historiques vus non lisibles sur ce navigateur.' };
  }
}

export function useHistoryAcknowledgments() {
  const [state, setState] = useState(readSeen);
  useEffect(() => {
    const refresh = () => setState(readSeen());
    window.addEventListener('storage', refresh);
    window.addEventListener(CHANGED, refresh);
    return () => {
      window.removeEventListener('storage', refresh);
      window.removeEventListener(CHANGED, refresh);
    };
  }, []);
  const acknowledge = useCallback((keys) => {
    const valid = keys.filter((key) => typeof key === 'string' && key.length > 0 && key.length <= 8192);
    if (!valid.length) return;
    try {
      const prior = readSeen();
      if (prior.error) throw new Error();
      const combined = [...new Set([...prior.keys, ...valid])].slice(-LIMIT);
      window.localStorage.setItem(HISTORY_SEEN_KEY, JSON.stringify({ schema_version: 1, keys: combined }));
      window.dispatchEvent(new Event(CHANGED));
    } catch (_error) {
      setState((previous) => ({ ...previous, error: 'Confirmation non enregistrée : message historique conservé.' }));
    }
  }, []);
  return { seen: state.keys, acknowledge, error: state.error };
}
