import { useCallback, useEffect, useState } from 'react';

const identity = (value) => value;

// Navigation preferences only: never cache measurements, command drafts or authority.
export default function useElyseUiState(key, fallback, choices, enabled = true, normalize = identity) {
  const validate = useCallback((value) => {
    const normalized = normalize(value);
    return choices.includes(normalized) ? normalized : fallback;
  }, [choices, fallback, normalize]);
  const [value, setValue] = useState(() => {
    if (enabled) {
      try { return validate(window.localStorage.getItem(key)); } catch { /* Storage is optional. */ }
    }
    return fallback;
  });
  useEffect(() => {
    if (enabled) {
      try { window.localStorage.setItem(key, value); } catch { /* Memory-only navigation still works. */ }
    }
  }, [enabled, key, value]);
  const choose = useCallback((selection) => {
    const next = validate(selection);
    // Write before navigation can unmount this panel or unload the document.
    if (enabled) {
      try { window.localStorage.setItem(key, next); } catch { /* Memory-only navigation still works. */ }
    }
    setValue(next);
  }, [enabled, key, validate]);
  return [value, choose];
}
