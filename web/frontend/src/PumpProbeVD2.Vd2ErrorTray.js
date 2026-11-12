function Vd2ErrorTray({ errors, activeErrorId, onPrevious, onNext, onCopy, onDismiss, onClear }) {
  if (!errors.length) return null;
  const activeIndex = Math.max(0, errors.findIndex((entry) => entry.id === activeErrorId));
  const entry = errors[activeIndex];
  return (
    <section className="vd2-error-tray" role="alert" aria-live="assertive">
      <div className="vd2-error-tray-meta">
        <strong>{entry.source}</strong>
        <span>{activeIndex + 1} / {errors.length}</span>
        <time dateTime={new Date(entry.timestamp).toISOString()}>{new Date(entry.timestamp).toLocaleTimeString()}</time>
      </div>
      <pre>{entry.message}</pre>
      <div className="vd2-error-tray-actions">
        <button type="button" onClick={onPrevious} disabled={errors.length < 2} title="Previous error" aria-label="Previous error">&lt;</button>
        <button type="button" onClick={onNext} disabled={errors.length < 2} title="Next error" aria-label="Next error">&gt;</button>
        <button type="button" onClick={() => onCopy(entry.message)} title="Copy error" aria-label="Copy error">Copy</button>
        <button type="button" onClick={() => onDismiss(entry.id)} title="Close this error" aria-label="Close this error">x</button>
        <button type="button" onClick={onClear}>Clear all</button>
      </div>
    </section>
  );
}

export {
  Vd2ErrorTray,
};
