import React, { useRef } from 'react';
import { editRoiBounds } from '../vd2RoiMath';

const HANDLES = {
  nw: 'top left', n: 'top', ne: 'top right', e: 'right',
  se: 'bottom right', s: 'bottom', sw: 'bottom left', w: 'left',
};

export default function VD2RoiEditor({ bounds, width, height, pointFromEvent, onChange,
  onSelect, selected = true, type = 'rectangle', color = '#ffe176', label = 'ROI' }) {
  const drag = useRef(null);
  const allowedHandles = type === 'vertical' ? ['w', 'e'] : type === 'horizontal' ? ['n', 's'] : Object.keys(HANDLES);
  const begin = (event, handle) => {
    if (event.button !== 0) return;
    const point = pointFromEvent(event);
    if (!point) return;
    event.preventDefault();
    event.stopPropagation();
    onSelect?.();
    drag.current = { handle, point, bounds: { ...bounds }, pointerId: event.pointerId, target: event.currentTarget };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    event.currentTarget.focus?.({ preventScroll: true });
  };
  const move = event => {
    const current = drag.current;
    if (!current || event.pointerId !== current.pointerId) return;
    event.stopPropagation();
    const point = pointFromEvent(event);
    if (point) onChange(editRoiBounds(current.bounds, point.x - current.point.x, point.y - current.point.y,
      current.handle, width, height));
  };
  const finish = event => {
    if (!drag.current || event.pointerId !== drag.current.pointerId) return;
    move(event);
    const { target, pointerId } = drag.current;
    drag.current = null;
    if (target.hasPointerCapture?.(pointerId)) target.releasePointerCapture(pointerId);
    event.stopPropagation();
  };
  const keyDown = (event, handle) => {
    const directions = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    const direction = directions[event.key];
    if (!direction) return;
    event.preventDefault();
    event.stopPropagation();
    onSelect?.();
    const step = event.shiftKey ? 10 : 1;
    onChange(editRoiBounds(bounds, direction[0] * step, direction[1] * step, handle, width, height));
  };
  const cx = (bounds.x0 + bounds.x1 + 1) / 2;
  const cy = (bounds.y0 + bounds.y1 + 1) / 2;
  return (
    <g className={`vd2-roi-editor ${selected ? 'is-selected' : ''}`} onPointerMove={move}
      onPointerUp={finish} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}>
      <rect className="vd2-roi-body" role="button" tabIndex="0" aria-label={`Move ${label}`}
        x={bounds.x0} y={bounds.y0} width={bounds.x1 - bounds.x0 + 1} height={bounds.y1 - bounds.y0 + 1}
        stroke={color} onPointerDown={event => begin(event, 'move')} onKeyDown={event => keyDown(event, 'move')}>
        <title>Drag to move. Arrow keys move 1 pixel; Shift + arrows move 10.</title>
      </rect>
      {selected && allowedHandles.map(handle => {
        const x = handle.includes('w') ? bounds.x0 : handle.includes('e') ? bounds.x1 + 1 : cx;
        const y = handle.includes('n') ? bounds.y0 : handle.includes('s') ? bounds.y1 + 1 : cy;
        return <g key={handle} className={`vd2-roi-handle vd2-roi-handle-${handle}`}>
          <rect className="vd2-roi-hit" x={x - 9} y={y - 9} width="18" height="18"
            role="button" tabIndex="0" aria-label={`Resize ${label} ${HANDLES[handle]}`}
            onPointerDown={event => begin(event, handle)} onKeyDown={event => keyDown(event, handle)} />
          <rect className="vd2-roi-grip" x={x - 4} y={y - 4} width="8" height="8" stroke={color} />
        </g>;
      })}
    </g>
  );
}
