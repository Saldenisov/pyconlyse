import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import TopasControl from './TopasControl';
import Equipment from './Equipment';
import { readTopas, sendTopas } from './topasClient';

jest.mock('./topasClient', () => ({ readTopas: jest.fn(), sendTopas: jest.fn(), acknowledgeTopasError: jest.fn(), TOPAS_DEVICE: 'manip/laser/topas_t21082' }));
const snapshot = () => ({ fresh: true, age_s: .1, stale_after_s: 5, operation: null, data: {
  serial_number: 'T21082', authentication: { CallerHasAccess: true },
  output: { Wavelength: 600, SignalWavelength: 1200, IdlerWavelength: 2237, Interaction: 'SH-SIG',
    IsWavelengthStrict: true, IsWavelengthSettingInProgress: false, IsWaitingForUserAction: false, Messages: [] },
  shutter: { IsShutterOpen: false, IsInterlockOpen: false },
  interactions: [{ Type: 'SH-SIG', OutputRange: { From: 570, To: 810 } }],
  motors: [{ Index: 1, Title: 'Crystal 1', UnitName: 'deg', ActualPositionInUnits: 2.5, TargetPositionInUnits: 2.5 }],
} });
const show = () => render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><TopasControl /></MemoryRouter>);
beforeEach(() => { localStorage.clear(); jest.clearAllMocks(); readTopas.mockResolvedValue(snapshot()); sendTopas.mockResolvedValue({ result: 'request-1' }); });
afterEach(() => jest.useRealTimers());

test('page reads state without sending startup commands and exposes installed controls', async () => {
  show();
  expect(await screen.findByRole('button', { name: 'Shutter CLOSED · Open' })).toBeEnabled();
  expect(screen.getByRole('spinbutton', { name: 'Wavelength nm' })).toHaveValue(600);
  expect(screen.getByRole('form', { name: 'Motor 1 Crystal 1' })).toBeInTheDocument();
  expect(screen.getByRole('combobox', { name: 'Interaction' })).toHaveTextContent('SH-SIG');
  expect(sendTopas).not.toHaveBeenCalled();
});

test('polling preserves operator drafts and Enter submits only the selected motor', async () => {
  jest.useFakeTimers(); show();
  await act(async () => {});
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Wavelength nm' }), { target: { value: '650' } });
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Crystal 1 target' }), { target: { value: '3' } });
  const next = snapshot(); next.data.output.Wavelength = 601; next.data.motors[0].TargetPositionInUnits = 4;
  readTopas.mockResolvedValue(next);
  await act(async () => { jest.advanceTimersByTime(1100); });
  expect(screen.getByRole('spinbutton', { name: 'Wavelength nm' })).toHaveValue(650);
  expect(screen.getByRole('spinbutton', { name: 'Crystal 1 target' })).toHaveValue(3);
  fireEvent.submit(screen.getByRole('form', { name: 'Motor 1 Crystal 1' }));
  await act(async () => {});
  expect(sendTopas).toHaveBeenCalledTimes(1);
  expect(sendTopas).toHaveBeenCalledWith('set_motor_position', [1, 3, 'units']);
});

test('wavelength form prevents duplicate dispatch while the request is pending', async () => {
  sendTopas.mockImplementation(() => new Promise(() => {}));
  show();
  await screen.findByRole('button', { name: 'Shutter CLOSED · Open' });
  const input = screen.getByRole('spinbutton', { name: 'Wavelength nm' });
  fireEvent.change(input, { target: { value: '650' } });
  fireEvent.submit(input.closest('form')); fireEvent.submit(input.closest('form'));
  expect(sendTopas).toHaveBeenCalledTimes(1);
  expect(sendTopas).toHaveBeenCalledWith('set_wavelength', [650]);
});

test('stale status retains last data but disables hardware operations', async () => {
  readTopas.mockResolvedValue({ ...snapshot(), age_s: 10 });
  show();
  expect(await screen.findByRole('button', { name: 'Shutter unverified' })).toBeDisabled();
  expect(screen.getByRole('spinbutton', { name: 'Wavelength nm' })).toHaveValue(600);
  expect(screen.getByRole('spinbutton', { name: 'Wavelength nm' })).toBeDisabled();
  expect(screen.getByText('Last known output')).toBeInTheDocument();
  expect(sendTopas).not.toHaveBeenCalled();
});

test('command error remains readable after a successful status poll', async () => {
  jest.useFakeTimers(); sendTopas.mockRejectedValue(new Error('Command denied'));
  show(); await act(async () => {});
  fireEvent.click(screen.getByRole('button', { name: 'Shutter CLOSED · Open' }));
  await act(async () => {});
  expect(screen.getByRole('alert')).toHaveTextContent('Command denied');
  await act(async () => { jest.advanceTimersByTime(1100); });
  expect(screen.getByRole('alert')).toHaveTextContent('Command denied');
});

test('pending poll is cancelled on unmount and does not create overlapping requests', async () => {
  jest.useFakeTimers(); let signal;
  readTopas.mockImplementation(value => { signal = value; return new Promise(() => {}); });
  const view = show();
  await act(async () => { jest.advanceTimersByTime(2000); });
  expect(readTopas).toHaveBeenCalledTimes(1);
  view.unmount();
  expect(signal.aborted).toBe(true);
});

test('saving and loading a wavelength only edits the draft without a hardware command', async () => {
  show();
  const save = await screen.findByRole('button', { name: 'Save current wavelength' });
  await waitFor(() => expect(save).toBeEnabled());
  fireEvent.click(save);
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Wavelength nm' }), { target: { value: '650' } });
  fireEvent.click(screen.getByRole('button', { name: '600.00 nm · SH-SIG' }));
  expect(screen.getByRole('spinbutton', { name: 'Wavelength nm' })).toHaveValue(600);
  expect(sendTopas).not.toHaveBeenCalled();
});

test('Equipment TOPAS card opens the dedicated control page', async () => {
  render(<MemoryRouter initialEntries={['/equipment']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    <Routes><Route path="/equipment" element={<Equipment />} /><Route path="/topas" element={<TopasControl />} /></Routes>
  </MemoryRouter>);
  fireEvent.click(screen.getByRole('heading', { name: 'TOPAS' }));
  await waitFor(() => expect(screen.getByRole('heading', { name: /TOPAS T21082/ })).toBeInTheDocument());
});
