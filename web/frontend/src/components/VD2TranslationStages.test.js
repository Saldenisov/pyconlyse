import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import VD2TranslationStages from './VD2TranslationStages';
import { fetchWithHardwareApproval } from '../api/csrfRequest';

jest.mock('../api/csrfRequest', () => ({ fetchWithHardwareApproval: jest.fn() }));

const originalFetch = global.fetch;
const response = (payload) => ({ ok: true, status: 200, json: async () => payload });

beforeEach(() => {
  fetchWithHardwareApproval.mockReset();
  fetchWithHardwareApproval.mockResolvedValue(response({ success: true, result: '0' }));
  global.fetch = jest.fn().mockResolvedValue(response({
    success: true,
    zaber_mirror: {
      state: 'ON', status: 'Connected', position_mm: 12.5,
      minimum_mm: 0, maximum_mm: 50.8,
    },
    owis_sample: {
      state: 'ON', axis_state: 'ON', axis: 2, position_mm: 36,
      minimum_mm: -40, maximum_mm: 260,
    },
  }));
});

afterEach(() => { global.fetch = originalFetch; });

test('reads two translation stages without moving either one', async () => {
  render(<VD2TranslationStages />);
  expect(await screen.findByText('12.5000 mm')).toBeInTheDocument();
  expect(screen.getByText('36.0000 mm')).toBeInTheDocument();
  expect(screen.getByText(/VD2 sample axis 2/)).toBeInTheDocument();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('sends an absolute Zaber target in millimetres', async () => {
  render(<VD2TranslationStages showOwis={false} />);
  const mirror = await screen.findByRole('region', { name: 'Zaber mirror translation stage' });
  fireEvent.change(within(mirror).getByLabelText('Absolute target (mm)'), {
    target: { value: '20.25' },
  });
  fireEvent.click(within(mirror).getByRole('button', { name: 'Move' }));
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  expect(fetchWithHardwareApproval.mock.calls[0][0]).toBe(
    '/api/device/manip/VD2/Zaber/command/MoveAbsoluteMm'
  );
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body)).toEqual({ args: 20.25 });
});

test('routes VD2 sample motion to OWIS axis two', async () => {
  render(<VD2TranslationStages />);
  const sample = await screen.findByRole('region', { name: 'OWIS sample translation stage' });
  fireEvent.change(within(sample).getByLabelText('Absolute target (mm)'), {
    target: { value: '40.5' },
  });
  fireEvent.click(within(sample).getByRole('button', { name: 'Move sample' }));
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  expect(fetchWithHardwareApproval.mock.calls[0][0]).toBe(
    '/api/device/manip/general/DS_OWIS_Aggregator/command/move_axis'
  );
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body)).toEqual({ args: [2, 40.5] });
});
