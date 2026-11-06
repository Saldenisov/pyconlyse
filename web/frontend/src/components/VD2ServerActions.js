import React, { useEffect, useRef, useState } from 'react';
import { fetchWithHardwareApproval } from '../api/csrfRequest';
import './VD2ServerActions.css';

export default function VD2ServerActions({
  label, servers, onRestart, className, ariaLabel, children,
}) {
  const cardRef = useRef(null);
  const [menu, setMenu] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!menu) return undefined;
    const closeOutside = (event) => {
      if (!cardRef.current?.contains(event.target)) setMenu(null);
    };
    const closeEscape = (event) => {
      if (event.key === 'Escape') setMenu(null);
    };
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeEscape);
    };
  }, [menu]);

  const openMenu = (event) => {
    event.preventDefault();
    const bounds = cardRef.current.getBoundingClientRect();
    setMenu({
      left: Math.max(0, Math.min(event.clientX - bounds.left, bounds.width - 220)),
      top: Math.max(0, event.clientY - bounds.top),
    });
  };

  const restart = async (server) => {
    setMenu(null);
    if (!window.confirm(`Restart ${server.name} for ${label}? Motion and control will be interrupted.`)) return;
    setBusy(true);
    setMessage('');
    try {
      const response = await fetchWithHardwareApproval('/api/server/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ action: 'restart', server_name: server.name }),
      });
      const payload = await response.json();
      if (!response.ok || payload.success !== true || payload.running !== true) {
        throw new Error(payload.error || `${server.name} did not restart`);
      }
      setMessage(`${server.name} is running`);
      if (onRestart) await onRestart();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section ref={cardRef} className={`${className || ''} vd2-restartable`} aria-label={ariaLabel}
      onContextMenu={openMenu}>
      {children}
      <small className="vd2-restart-hint">Right-click to restart the Device Server.</small>
      {busy && <p className="vd2-restart-message" role="status">Restarting Device Server…</p>}
      {message && <p className="vd2-restart-message" role="status">{message} <button type="button" onClick={() => setMessage('')} aria-label="Dismiss server message">×</button></p>}
      {menu && (
        <div className="vd2-server-menu" role="menu" style={{ left: menu.left, top: menu.top }}>
          {servers.map((server) => (
            <button key={server.name} type="button" role="menuitem" disabled={busy}
              onClick={() => restart(server)}>
              Restart {server.label || server.name}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
