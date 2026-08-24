// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

jest.mock('plotly.js-dist', () => ({
  __esModule: true,
  default: {
    newPlot: () => Promise.resolve(),
    react: () => Promise.resolve(),
    restyle: () => Promise.resolve(),
    purge: () => undefined,
    Plots: { resize: () => undefined },
  },
}));
