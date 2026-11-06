import React, { useState } from 'react';
import './TreatmentPanel.css';

export default function DerivedSourcePanel({ sources, busy, error, onRemove, onMove, onClear, onDerive }) {
  const [method, setMethod] = useState('average');
  return <section className="pp-derived-panel" aria-label="Derived dataset sources">
    <strong>Combine loaded files</strong>
    <span> - {sources.length} source(s), in the order shown</span>
    {sources.length ? <ol>{sources.map((source, index) => <li key={`${source.path}:${source.source_sha256}`}>
      <span className="pp-derived-source-label" title={source.path}>{source.file_name || source.path} - {source.source_sha256.slice(0, 10)}</span>
      <button type="button" aria-label={`Move source ${index + 1} up`} disabled={busy || index === 0} onClick={() => onMove(index, -1)}>Up</button>
      <button type="button" aria-label={`Move source ${index + 1} down`} disabled={busy || index === sources.length - 1} onClick={() => onMove(index, 1)}>Down</button>
      <button type="button" aria-label={`Remove source ${index + 1}`} disabled={busy} onClick={() => onRemove(index)}>Remove</button>
    </li>)}</ol> : <p>Load OD files in Files to add sources.</p>}
    <label>Combine method<select value={method} disabled={busy} onChange={(event) => setMethod(event.target.value)}>
      <option value="average">Arithmetic average</option><option value="merge">Merge spectral segments</option>
    </select></label>
    <button type="button" disabled={busy || sources.length < 2} onClick={() => onDerive(method)}>{busy ? 'Combining...' : 'Combine'}</button>
    <button type="button" disabled={busy || !sources.length} onClick={onClear}>Clear sources</button>
    <p>{method === 'average' ? 'Average requires matching wavelength axes.' : 'Merge requires identical delay axes; wavelength segments follow source order.'}</p>
    {error && <p role="alert" className="pp-treatment-error">{error}</p>}
  </section>;
}
