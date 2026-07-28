import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the PyConlyse home page', () => {
  render(<App />);
  expect(
    screen.getByRole('heading', { name: /welcome to pyconlyse/i })
  ).toBeInTheDocument();
});
