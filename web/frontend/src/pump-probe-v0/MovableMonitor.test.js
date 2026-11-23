import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import MovableMonitor from './MovableMonitor';

const pointer = window.PointerEvent;
beforeEach(() => { localStorage.clear(); window.PointerEvent = MouseEvent; });
afterEach(() => { window.PointerEvent = pointer; });

function show() {
  const command = jest.fn();
  const view = render(<div><MovableMonitor><button onClick={command}>Read data</button></MovableMonitor></div>);
  const panel = screen.getByRole('region', { name: 'Movable current plots' });
  panel.getBoundingClientRect = () => ({ width: 260, height: 620 });
  panel.parentElement.getBoundingClientRect = () => ({ width: 1000, height: 1000 });
  return { panel, command, view };
}

test('dragging the window changes position, persists it, and sends no data command', () => {
  const { panel, command, view } = show();
  const handle = screen.getByRole('button', { name: 'Move current plots' });
  fireEvent.pointerDown(handle, { button: 0, clientX: 10, clientY: 10 });
  fireEvent.pointerMove(handle, { clientX: 160, clientY: 90 });
  fireEvent.pointerUp(handle);
  expect(panel.style.transform).toBe('translate(150px, 80px)');
  expect(command).not.toHaveBeenCalled();
  view.unmount();
  const restored = show();
  expect(restored.panel.style.transform).toBe('translate(150px, 80px)');
});

test('resize is horizontal and bounded; reset restores the initial layout without commands', () => {
  const { panel, command } = show();
  const resize = screen.getByRole('button', { name: 'Resize current plots' });
  fireEvent.pointerDown(resize, { button: 0, clientX: 260, clientY: 620 });
  fireEvent.pointerMove(resize, { clientX: 800, clientY: 1000 });
  fireEvent.pointerUp(resize);
  expect(panel.style.width).toBe('400px');
  fireEvent.click(screen.getByRole('button', { name: 'Reset plot position' }));
  expect(panel.style.width).toBe('260px');
  expect(panel.style.transform).toBe('translate(0px, 0px)');
  expect(command).not.toHaveBeenCalled();
});

test('move handle clamps the window to its workspace and supports keyboard positioning', () => {
  const { panel } = show();
  const handle = screen.getByRole('button', { name: 'Move current plots' });
  fireEvent.pointerDown(handle, { button: 0, clientX: 0, clientY: 0 });
  fireEvent.pointerMove(handle, { clientX: 5000, clientY: 5000 });
  fireEvent.pointerUp(handle);
  expect(panel.style.transform).toBe('translate(740px, 380px)');
  fireEvent.keyDown(handle, { key: 'ArrowLeft' });
  expect(panel.style.transform).toBe('translate(730px, 380px)');
});
