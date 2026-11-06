import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import VD2RoiEditor from './VD2RoiEditor';

const originalPointerEvent = window.PointerEvent;
beforeAll(() => {
  window.PointerEvent = class extends MouseEvent {
    constructor(type, options) {
      super(type, options);
      Object.defineProperty(this, 'pointerId', { value: options.pointerId || 1 });
    }
  };
});
afterAll(() => { window.PointerEvent = originalPointerEvent; });

function ControlledRoi({ type = 'rectangle' }) {
  const [bounds, setBounds] = useState({ x0: 20, x1: 39, y0: 10, y1: 29 });
  return <svg><VD2RoiEditor bounds={bounds} width={100} height={80} type={type}
    pointFromEvent={event => ({ x: event.clientX, y: event.clientY })} onChange={setBounds} label="test ROI" /></svg>;
}

test('pointer drag uses original grab point through controlled rerenders', () => {
  render(<ControlledRoi />);
  const body = screen.getByRole('button', { name: 'Move test ROI' });
  fireEvent.pointerDown(body, { button: 0, pointerId: 1, clientX: 30, clientY: 20 });
  fireEvent.pointerMove(body, { pointerId: 1, clientX: 50, clientY: 35 });
  expect(body).toHaveAttribute('x', '40');
  expect(body).toHaveAttribute('y', '25');
  fireEvent.pointerMove(body, { pointerId: 1, clientX: 60, clientY: 40 });
  fireEvent.pointerUp(body, { pointerId: 1, clientX: 60, clientY: 40 });
  expect(body).toHaveAttribute('x', '50');
  expect(body).toHaveAttribute('y', '30');
  expect(body).toHaveAttribute('width', '20');
  expect(body).toHaveAttribute('height', '20');
});

test('corner drag resizes until camera boundary without moving opposite corner', () => {
  render(<ControlledRoi />);
  const handle = screen.getByRole('button', { name: 'Resize test ROI bottom right' });
  fireEvent.pointerDown(handle, { button: 0, pointerId: 1, clientX: 40, clientY: 30 });
  fireEvent.pointerMove(handle, { pointerId: 1, clientX: 140, clientY: 130 });
  fireEvent.pointerUp(handle, { pointerId: 1, clientX: 140, clientY: 130 });
  const body = screen.getByRole('button', { name: 'Move test ROI' });
  expect(body).toHaveAttribute('x', '20');
  expect(body).toHaveAttribute('y', '10');
  expect(body).toHaveAttribute('width', '80');
  expect(body).toHaveAttribute('height', '70');
});

test('keyboard moves and resizes ROI, while axis-spanning ROI exposes only applicable handles', () => {
  render(<ControlledRoi type="vertical" />);
  const body = screen.getByRole('button', { name: 'Move test ROI' });
  fireEvent.keyDown(body, { key: 'ArrowRight', shiftKey: true });
  expect(body).toHaveAttribute('x', '30');
  fireEvent.keyDown(screen.getByRole('button', { name: 'Resize test ROI left' }), { key: 'ArrowRight' });
  expect(body).toHaveAttribute('x', '31');
  expect(body).toHaveAttribute('width', '19');
  expect(screen.queryByRole('button', { name: 'Resize test ROI top' })).not.toBeInTheDocument();
});
