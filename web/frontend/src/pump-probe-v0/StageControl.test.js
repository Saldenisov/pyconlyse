import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { StageControl } from './components.HeatmapSelectorChart';

jest.mock('./components.PlotPanel', () => ({ PlotlyChart: () => null }));
const pointer = window.PointerEvent;
beforeEach(() => { window.PointerEvent = MouseEvent; });
afterEach(() => { window.PointerEvent = pointer; });

test.each([[100, -900], [600, -400], [1100, 100]])('horizontal rail maps X=%s to %s mm and moves only after Accept', (clientX, expected) => {
  const move = jest.fn();
  const { container } = render(<StageControl orientation="horizontal" positionMm={-50} setPositionMm={-50}
    stepPs={1} zeroMm={0} onPositionChange={move} onStop={jest.fn()}
    onStepChange={jest.fn()} onZeroChange={jest.fn()} onOpenConfig={jest.fn()} />);
  expect(screen.getByRole('region', { name: 'Delay line' })).toHaveClass('pp-stage-panel-horizontal');
  container.querySelector('.pp-stage-rail').getBoundingClientRect = () => ({ left: 100, top: 500, width: 1000, height: 80 });
  const carriage = container.querySelector('.pp-stage-carriage');
  fireEvent.pointerDown(carriage, { button: 0, clientX, clientY: 900 });
  fireEvent.pointerUp(carriage);
  expect(move).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Accept' }));
  expect(move).toHaveBeenCalledTimes(1);
  expect(move).toHaveBeenCalledWith(expected);
});
