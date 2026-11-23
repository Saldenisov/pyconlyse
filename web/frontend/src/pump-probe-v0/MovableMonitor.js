import React, { useCallback, useLayoutEffect, useRef, useState } from 'react';

const KEY = 'v0.current-monitor-layout.v1';
const initial = { width: 260, x: 0, y: 0 };
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
function loadLayout() {
  try {
    const value = JSON.parse(localStorage.getItem(KEY));
    if (value && ['width', 'x', 'y'].every(key => Number.isFinite(value[key]))) {
      return { width: clamp(value.width, 210, 400), x: Math.max(0, value.x), y: Math.max(0, value.y) };
    }
  } catch (_) { /* Layout preferences must not prevent displaying data. */ }
  return initial;
}

export default function MovableMonitor({ children }) {
  const [layout, setLayout] = useState(loadLayout);
  const current = useRef(layout);
  const panel = useRef(null);
  const gesture = useRef(null);
  const update = useCallback(value => { current.current = value; setLayout(value); }, []);
  const save = () => {
    try { localStorage.setItem(KEY, JSON.stringify(current.current)); } catch (_) { /* Optional preference. */ }
  };
  useLayoutEffect(() => {
    const keepInside = () => {
      const parent = panel.current?.parentElement.getBoundingClientRect();
      const rect = panel.current?.getBoundingClientRect();
      if (!parent?.width || !rect?.height) return;
      const value = current.current;
      const next = { ...value, x: clamp(value.x, 0, Math.max(0, parent.width - rect.width)),
        y: clamp(value.y, 0, Math.max(0, parent.height - rect.height)) };
      if (next.x !== value.x || next.y !== value.y) update(next);
    };
    keepInside();
    window.addEventListener('resize', keepInside);
    return () => window.removeEventListener('resize', keepInside);
  }, [update]);
  const begin = (event, kind) => {
    if (event.button !== 0) return;
    event.preventDefault();
    const bounds = panel.current.parentElement.getBoundingClientRect();
    gesture.current = { kind, pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY,
      layout: current.current, bounds, height: panel.current.getBoundingClientRect().height };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const move = event => {
    const start = gesture.current;
    if (!start || event.pointerId !== start.pointerId) return;
    const dx = event.clientX - start.clientX;
    const dy = event.clientY - start.clientY;
    const width = start.kind === 'resize' ? clamp(start.layout.width + dx, 210, Math.min(400, start.bounds.width)) : start.layout.width;
    const height = start.height + 2 * (width - start.layout.width);
    update({ width,
      x: clamp(start.layout.x + (start.kind === 'move' ? dx : 0), 0, Math.max(0, start.bounds.width - width)),
      y: clamp(start.layout.y + (start.kind === 'move' ? dy : 0), 0, Math.max(0, start.bounds.height - height)) });
  };
  const finish = () => { gesture.current = null; save(); };
  const keyboard = (event, kind) => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    const value = current.current;
    const bounds = panel.current.parentElement.getBoundingClientRect();
    const step = event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -10 : 10;
    if (kind === 'resize') {
      const width = clamp(value.width + step, 210, Math.min(400, bounds.width || 400));
      update({ width, x: clamp(value.x, 0, Math.max(0, bounds.width - width)),
        y: clamp(value.y, 0, Math.max(0, bounds.height - panel.current.offsetHeight - 2 * (width - value.width))) });
    }
    else update({ ...value,
      x: clamp(value.x + (['ArrowLeft', 'ArrowRight'].includes(event.key) ? step : 0), 0, Math.max(0, bounds.width - value.width)),
      y: clamp(value.y + (['ArrowUp', 'ArrowDown'].includes(event.key) ? step : 0), 0, Math.max(0, bounds.height - panel.current.offsetHeight)) });
    save();
  };
  return <div ref={panel} className="pp-current-monitor-window pp-left-column" role="region" aria-label="Movable current plots"
    style={{ width: layout.width, transform: `translate(${layout.x}px, ${layout.y}px)` }}>
    <div className="pp-current-window-tools">
      <button type="button" className="pp-current-drag" aria-label="Move current plots" title="Drag to move"
        onPointerDown={event => begin(event, 'move')} onPointerMove={move} onPointerUp={finish} onPointerCancel={finish}
        onKeyDown={event => keyboard(event, 'move')}>⠿ Current</button>
      <button type="button" aria-label="Reset plot position" title="Reset position and width" onClick={() => { update(initial); save(); }}>↺</button>
    </div>
    {children}
    <button type="button" className="pp-current-resize" aria-label="Resize current plots" title="Drag horizontally to resize"
      onPointerDown={event => begin(event, 'resize')} onPointerMove={move} onPointerUp={finish} onPointerCancel={finish}
      onKeyDown={event => keyboard(event, 'resize')}>↔</button>
  </div>;
}
