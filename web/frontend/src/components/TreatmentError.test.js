import { render, screen } from '@testing-library/react';
import TreatmentError from './TreatmentError';
import { TREATMENT_AUTH_MESSAGE } from '../api/treatmentClient';

test('shows a server rejection without a login link', () => {
  render(<TreatmentError message={TREATMENT_AUTH_MESSAGE} />);
  expect(screen.getByRole('alert')).toHaveTextContent(TREATMENT_AUTH_MESSAGE);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

test('does not suggest sign-in for processing failures', () => {
  render(<TreatmentError message="Input file is missing" />);
  expect(screen.getByRole('alert')).toHaveTextContent('Input file is missing');
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});
