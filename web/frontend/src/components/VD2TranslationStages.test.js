import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import VD2TranslationStages, { VD2SampleHolder } from './VD2TranslationStages';
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

test('compact acquisition control moves only VD2 sample axis two after an explicit click', async () => {
  render(<VD2SampleHolder />);
  const sample = await screen.findByRole('form', { name: 'OWIS target' });
  await within(sample).findByText('36.0000 mm');
  expect(screen.queryByRole('heading', { name: 'Zaber mirror' })).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'OWIS sample holder' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Stop sample' })).not.toBeInTheDocument();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
  fireEvent.change(within(sample).getByLabelText('Enter OWIS target (mm)'), { target: { value: '41.5' } });
  fireEvent.click(within(sample).getByRole('button', { name: 'Move to Position' }));
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body)).toEqual({ args: [2, 41.5] });
});

test('sample motion is blocked while HIS measurement is active', async () => {
  render(<VD2SampleHolder disabled />);
  await screen.findByText('36.0000 mm');
  expect(screen.getByRole('button', { name: 'Move to Position' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Enter OWIS target (mm)'), { target: { value: '41.5' } });
  fireEvent.submit(screen.getByRole('form', { name: 'OWIS target' }));
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('compact position follows readbacks and hides the previous value when reading fails', async () => {
  jest.useFakeTimers();
  const view = render(<VD2SampleHolder />);
  try {
    await screen.findByText('36.0000 mm');
    global.fetch.mockRejectedValue(new Error('Stage read timed out'));
    await act(async () => { jest.advanceTimersByTime(2500); });
    expect(screen.getByLabelText('OWIS current position')).toHaveTextContent('Unavailable');
    expect(screen.queryByText('36.0000 mm')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Move to Position' })).toBeDisabled();
    global.fetch.mockResolvedValue(response({ success: true,
      owis_sample: { state: 'ON', axis_state: 'ON', position_mm: 37, minimum_mm: -40, maximum_mm: 260 },
    }));
    await act(async () => { jest.advanceTimersByTime(2500); });
    expect(screen.getByLabelText('OWIS current position')).toHaveTextContent('37.0000 mm');
    expect(screen.getByRole('button', { name: 'Move to Position' })).toBeEnabled();
    expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
  } finally { view.unmount(); jest.useRealTimers(); }
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

test.each([
  ['Flash lamp', 0],
  ['Continuous lamp', 50],
])('%s preset sends its exact millimetre position', async (name, position) => {
  render(<VD2TranslationStages showOwis={false} />);
  const mirror = await screen.findByRole('region', { name: 'Zaber mirror translation stage' });
  const preset = await within(mirror).findByRole('button', { name: new RegExp(name) });
  await waitFor(() => expect(preset).toBeEnabled());
  fireEvent.click(preset);
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  expect(fetchWithHardwareApproval.mock.calls[0][0]).toBe(
    '/api/device/manip/VD2/Zaber/command/MoveAbsoluteMm'
  );
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body)).toEqual({ args: position });
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
    '/api/device/manip/general/DS_OWIS_PS90_IP/command/move_axis'
  );
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body)).toEqual({ args: [2, 40.5] });
});

test('right-click offers the exact Zaber Device Server without restarting it', async () => {
  render(<VD2TranslationStages showOwis={false} />);
  const mirror = await screen.findByRole('region', { name: 'Zaber mirror translation stage' });
  fireEvent.contextMenu(mirror);
  expect(within(mirror).getByRole('menuitem', { name: 'Restart DS_Zaber/1_Zaber' })).toBeInTheDocument();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('VD2 sample restart menu targets only the IP controller', async () => {
  render(<VD2TranslationStages />);
  const sample = await screen.findByRole('region', { name: 'OWIS sample translation stage' });
  fireEvent.contextMenu(sample);
  expect(within(sample).getByRole('menuitem', { name: 'Restart OWIS axis controller' })).toBeInTheDocument();
  expect(within(sample).getAllByRole('menuitem')).toHaveLength(1);
  expect(within(sample).queryByText(/aggregator/i)).not.toBeInTheDocument();
  expect(fetchWithHardwareApproval).not.toHaveBeenCalled();
});

test('stops VD2 sample axis two on the IP controller', async () => {
  global.fetch.mockResolvedValue(response({ success: true,
    owis_sample: { state: 'MOVING', axis_state: 'MOVING', position_mm: 39, minimum_mm: -40, maximum_mm: 260 },
  }));
  render(<VD2TranslationStages />);
  const sample = await screen.findByRole('region', { name: 'OWIS sample translation stage' });
  const stop = within(sample).getByRole('button', { name: 'Stop sample' });
  await waitFor(() => expect(stop).toBeEnabled());
  fireEvent.click(stop);
  await waitFor(() => expect(fetchWithHardwareApproval).toHaveBeenCalledTimes(1));
  expect(fetchWithHardwareApproval.mock.calls[0][0]).toBe('/api/device/manip/general/DS_OWIS_PS90_IP/command/stop_axis');
  expect(JSON.parse(fetchWithHardwareApproval.mock.calls[0][1].body)).toEqual({ args: 2 });
});
