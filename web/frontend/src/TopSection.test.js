import { render, screen } from '@testing-library/react';
import TopSection from './TopSection';
import { fetchSelection, TREATMENT_AUTH_MESSAGE } from './api/treatmentClient';

jest.mock('./api/treatmentClient', () => ({
  ...jest.requireActual('./api/treatmentClient'),
  fetchSelection: jest.fn(),
}));

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
