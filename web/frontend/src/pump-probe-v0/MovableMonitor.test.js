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
  panel.getBoundingClientRect = () => ({ width: 400, height: 500 });
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
  fireEvent.pointerDown(resize, { button: 0, clientX: 400, clientY: 500 });
  fireEvent.pointerMove(resize, { clientX: 1000, clientY: 1000 });
  fireEvent.pointerUp(resize);
  expect(panel.style.width).toBe('600px');
  fireEvent.click(screen.getByRole('button', { name: 'Reset plot position' }));
  expect(panel.style.width).toBe('400px');
  expect(panel.style.transform).toBe('translate(0px, 0px)');
  expect(command).not.toHaveBeenCalled();
});

test('move handle clamps the window to its workspace and supports keyboard positioning', () => {
  const { panel } = show();
  const handle = screen.getByRole('button', { name: 'Move current plots' });
  fireEvent.pointerDown(handle, { button: 0, clientX: 0, clientY: 0 });
  fireEvent.pointerMove(handle, { clientX: 5000, clientY: 5000 });
  fireEvent.pointerUp(handle);
  expect(panel.style.transform).toBe('translate(600px, 500px)');
  fireEvent.keyDown(handle, { key: 'ArrowLeft' });
  expect(panel.style.transform).toBe('translate(590px, 500px)');
});

test('the old narrow square layout gains the new width while preserving its position', () => {
  localStorage.setItem('v0.current-monitor-layout.v1', JSON.stringify({ width: 260, x: 70, y: 30 }));
  const { panel } = show();
  expect(panel.style.width).toBe('400px');
  expect(panel.style.transform).toBe('translate(70px, 30px)');
});
