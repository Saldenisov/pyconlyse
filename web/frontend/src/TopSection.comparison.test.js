import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Plotly from 'plotly.js-dist';
import { TreatmentContext } from './DataWindowVD2';
import { fetchSelection } from './api/treatmentClient';
import TopSection from './TopSection';
import { convertPreviewTime } from './treatmentPreviewCurves';

jest.mock('./DataWindowVD2', () => ({ TreatmentContext: require('react').createContext() }));
jest.mock('./api/treatmentClient', () => ({ fetchSelection: jest.fn() }));
jest.mock('plotly.js-dist', () => ({ react: jest.fn(), purge: jest.fn() }));

function selection(file, delay, unit, value) {
  return { selection: {
    active_data_type: 'DAT', assigned_data_types: ['DAT'], map_index: 0,
    file_info: { file_path: file, number_maps: 1, wavelengths_length: 1, timedelays_length: 1 },
    cursors: { x1: 0, x2: 1, y1: 0, y2: 1, x1_value: 620, x2_value: 620, y1_value: delay, y2_value: delay },
    heatmap: { z: [[value]], wavelengths: [620], timedelays: [delay] },
    kinetics: { x: [delay], y: [value], time_scale: unit },
    spectrum: { x: [620], y: [value] },
  } };
}

test('keeps unitless legacy DAT coordinates but does not mix them with calibrated delays', () => {
  expect(convertPreviewTime([0.5, 0.6], '??', '')).toEqual([0.5, 0.6]);
  expect(convertPreviewTime([0.5, 0.6], '??', 'ns')).toBeNull();
});

test('keeps a file’s curves in both previews after opening another file and can remove them', async () => {
  const originalResizeObserver = global.ResizeObserver;
  global.ResizeObserver = class { observe() {} disconnect() {} };
  try {
    Plotly.react.mockResolvedValue(undefined);
    fetchSelection
      .mockResolvedValueOnce(selection('E:\\test\\first.dat', 2, 'ns', 0.2))
      .mockResolvedValueOnce(selection('E:\\test\\second.dat', 0.002, 'µs', 0.3));
    function Workspace() {
      const [comparisonCurves, setComparisonCurves] = useState([]);
      const [selectionRefreshToken, refresh] = useState(0);
      return <TreatmentContext.Provider value={{ comparisonCurves, setComparisonCurves, selectionRefreshToken }}>
        <button onClick={() => refresh(1)}>Open second file</button>
        <TopSection />
      </TreatmentContext.Provider>;
    }
    render(<Workspace />);
    fireEvent.click(await screen.findByRole('button', { name: 'Add curves' }));
    fireEvent.click(screen.getByRole('button', { name: 'Open second file' }));

    await waitFor(() => {
      const plot = (name) => Plotly.react.mock.calls.filter(([node]) => node.classList.contains(name)).pop()?.[1];
      for (const [name, expectedX] of [['kinetics-plot', 0.002], ['spectrum-plot', 620]]) {
        const traces = plot(name);
        expect(traces).toHaveLength(2);
        expect(traces[1].name).toContain('first.dat');
        expect(traces[1].x[0]).toBeCloseTo(expectedX, 8);
        expect(traces[1].y).toEqual([0.2]);
      }
    });
    fireEvent.click(screen.getByRole('button', { name: /Remove first.dat/ }));
    await waitFor(() => {
      const [, traces] = Plotly.react.mock.calls.filter(([node]) => node.classList.contains('kinetics-plot')).pop();
      expect(traces).toHaveLength(1);
      expect(traces[0].name).toContain('second.dat');
    });
  } finally {
    global.ResizeObserver = originalResizeObserver;
  }
});
