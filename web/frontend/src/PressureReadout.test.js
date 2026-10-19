import React from 'react';
import { render, screen } from '@testing-library/react';
import PressureReadout, { pressureParts } from './PressureReadout';

test.each([
  [2.345e-9, { mantissa: '2,3', exponent: '−9' }],
  [-1.04e-8, { mantissa: '-1,0', exponent: '−8' }],
  [9.99e-9, { mantissa: '1,0', exponent: '−8' }],
  [1e-300, { mantissa: '1,0', exponent: '−300' }],
  [0, { mantissa: '0,0', exponent: null }],
])('rounds mantissa to one decimal without losing magnitude or sign: %p', (value, expected) => {
  expect(pressureParts(value)).toEqual(expected);
});

test.each([null, undefined, NaN, Infinity, -Infinity, '0', false])('keeps unavailable values unknown, not zero: %p', (value) => {
  expect(pressureParts(value)).toBeNull();
});

test('renders compact scientific pressure with unit and preserves unrounded value in tooltip', () => {
  render(<PressureReadout value={2.345e-9} label="CANON" />);
  expect(screen.getByLabelText('CANON')).toHaveTextContent('2,3 × 10−9');
  expect(screen.getByLabelText('CANON')).toHaveAttribute('title', 'Valeur avant arrondi : 2.345e-9 mbar');
  expect(screen.getByText('mbar')).toBeInTheDocument();
});

test('renders true zero without a meaningless exponent and missing value as dash', () => {
  const view = render(<PressureReadout value={0} label="CANON" />);
  expect(screen.getByLabelText('CANON')).toHaveTextContent('0,0');
  expect(screen.queryByText(/×/)).not.toBeInTheDocument();
  view.rerender(<PressureReadout value={null} label="CANON" />);
  expect(screen.getByLabelText('CANON')).toHaveTextContent('—');
});
