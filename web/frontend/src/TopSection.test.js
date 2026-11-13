import { fireEvent, render, screen } from '@testing-library/react';
import TopSection, { SelectionHeatmap } from './TopSection';
import { fetchSelection, TREATMENT_AUTH_MESSAGE } from './api/treatmentClient';

jest.mock('./api/treatmentClient', () => ({
  ...jest.requireActual('./api/treatmentClient'),
  fetchSelection: jest.fn(),
}));

test('drawing on ABS emits the original time row bounds', () => {
  const onReference = jest.fn();
  const before = window.PointerEvent;
  const resizeObserver = global.ResizeObserver;
  window.PointerEvent = MouseEvent;
  global.ResizeObserver = class {
    observe() {}
    disconnect() {}
  };
  const rect = jest.spyOn(HTMLElement.prototype, 'getBoundingClientRect')
    .mockReturnValue({ left: 0, top: 0, width: 300, height: 262 });
  try {
    const { container } = render(<SelectionHeatmap fillPanel drawingReference onReference={onReference}
      selection={{ file_info: { wavelengths_length: 2, timedelays_length: 101 } }} />);
    fireEvent.pointerDown(container.querySelector('.spectral-reference-draw'), { button: 0, clientY: 196 });
    fireEvent.pointerUp(window, { clientY: 155 });
    expect(onReference).toHaveBeenCalledWith({ start: 10, stop: 30 });
  } finally {
    rect.mockRestore();
    window.PointerEvent = before;
    global.ResizeObserver = resizeObserver;
  }
});

test('explains file assignment when the session has no inputs', async () => {
  fetchSelection.mockRejectedValue(new Error(
    'Assign at least one input file before using selection tools'
  ));
  render(<TopSection />);
  expect(await screen.findByText(
    'Choose a folder or manifest, then assign input files to preview.'
  )).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('keeps authentication failures distinct from an empty selection', async () => {
  fetchSelection.mockRejectedValue(new Error(TREATMENT_AUTH_MESSAGE));
  render(<TopSection />);
  expect(await screen.findByRole('alert')).toHaveTextContent(TREATMENT_AUTH_MESSAGE);
  expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
});
