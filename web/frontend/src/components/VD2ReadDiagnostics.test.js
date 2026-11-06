import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import VD2ReadDiagnostics from './VD2ReadDiagnostics';

function expand() {
  const details = screen.getByLabelText('Recent read warnings');
  details.open = true;
  fireEvent(details, new Event('toggle'));
  return details;
}

test('a brief warning remains readable after a successful read, and is marked resolved', () => {
  const view = render(<VD2ReadDiagnostics issues={{ acquisition: { label: 'Acquisition status', message: 'Read timed out' } }} />);
  expect(screen.getByText(/Read history \(1\).*1 active/)).toBeInTheDocument();
  view.rerender(<VD2ReadDiagnostics issues={{ acquisition: { label: 'Acquisition status', message: '' } }} />);
  expect(screen.getByText(/Read history \(1\).*resolved/)).toBeInTheDocument();
  expect(screen.queryByText('Read timed out')).not.toBeInTheDocument();
  const history = expand();
  expect(within(history).getByText('Read timed out')).toBeInTheDocument();
  expect(within(history).getByText(/Resolved at/)).toBeInTheDocument();
  fireEvent.click(within(history).getByRole('button', { name: 'Clear resolved history' }));
  expect(screen.queryByLabelText('Recent read warnings')).not.toBeInTheDocument();
});

test('repeated reads deduplicate; recovery of another scope does not clear an active problem', () => {
  const issues = { preview: { label: 'Frame preview', message: 'Frame unavailable' },
    acquisition: { label: 'Acquisition status', message: 'AcqStatus timed out' } };
  const view = render(<VD2ReadDiagnostics issues={issues} />);
  view.rerender(<VD2ReadDiagnostics issues={{ ...issues }} />);
  expect(screen.getByText(/Read history \(2\).*2 active/)).toBeInTheDocument();
  view.rerender(<VD2ReadDiagnostics issues={{ ...issues, preview: { ...issues.preview, message: '' } }} />);
  const history = expand();
  fireEvent.click(within(history).getByRole('button', { name: 'Clear resolved history' }));
  expect(screen.getByText(/Read history \(1\).*1 active/)).toBeInTheDocument();
  expect(within(history).getByText('AcqStatus timed out')).toBeInTheDocument();
  expect(within(history).getByRole('button', { name: 'Clear resolved history' })).toBeDisabled();
});

test('warning history is bounded to the ten most recent occurrences', () => {
  const view = render(<VD2ReadDiagnostics issues={{}} />);
  for (let i = 0; i < 12; i += 1) {
    view.rerender(<VD2ReadDiagnostics issues={{ preview: { label: 'Frame preview', message: `Failure ${i}` } }} />);
  }
  const history = expand();
  expect(within(history).getAllByRole('listitem')).toHaveLength(10);
  expect(within(history).queryByText('Failure 0')).not.toBeInTheDocument();
  expect(within(history).getByText('Failure 11')).toBeInTheDocument();
});
