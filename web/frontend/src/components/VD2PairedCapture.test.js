import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import VD2PairedCapture from './VD2PairedCapture';
import { fetchVd2 } from '../PumpProbeVD2.API_BASE';
import { DEFAULT_PAIRED_CORRECTION, pairedSpectralRegion } from '../vd2RoiMath';

jest.mock('../PumpProbeVD2.API_BASE', () => ({
  ...jest.requireActual('../PumpProbeVD2.API_BASE'), fetchVd2: jest.fn(),
}));

const band = { center_nm: 510, half_width_nm: 60, monitor_rows: 5 };
const props = {
  cameraIdle: true, live: false, correctionFixed: true, referenceConfirmed: true,
  correctionRange: { band, spectralBand: band },
  correction: { ...DEFAULT_PAIRED_CORRECTION, monitorRows: '5' },
  available: true,
  settings: { outputRoot: 'E:/DATA_VD2/test', runName: 'sample', reuseBruit: 'latest' },
  preview: { width: 10, height: 20 },
  onUpdate: jest.fn(), onStop: jest.fn(),
};

test('precision mode sends the wavelength band and operator phase', async () => {
  fetchVd2.mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, paired: { active: true } }) });
  const view = render(<VD2PairedCapture {...props} />);
  fireEvent.change(screen.getByLabelText('Stop condition'), { target: { value: 'precision' } });
  expect(screen.getByRole('button', { name: 'Measurement' })).toBeEnabled();
  view.rerender(<VD2PairedCapture {...props} roi={{ x0: 8, x1: 2, y0: 4, y1: 8 }} />);
  fireEvent.click(screen.getByLabelText('First frame with electrons'));
  fireEvent.click(screen.getByRole('button', { name: 'Measurement' }));
  await waitFor(() => expect(props.onUpdate).toHaveBeenCalledWith({ active: true }));
  const [url, options] = fetchVd2.mock.calls.at(-1);
  expect(url).toBe('/api/pump-probe-vd2/paired/start');
  expect(JSON.parse(options.body)).toMatchObject({
    first_map_with_electrons: false, mode: 'precision', target_mod: 2, method: 'lamp_matched', pair_limit: null,
    band,
    roi: { x0: 2, x1: 8, y0: 4, y1: 8, width: 10, height: 20 },
  });
});

test('shows signed OD and permits stopping the recording', () => {
  render(<VD2PairedCapture {...props} run={{ active: true, status: 'acquiring', mode: 'precision',
    job_id: 'job', target_mod: 2, first_map_with_electrons: true, trigger_source: 'external_rising',
    pairs_recorded: 200, pair_limit: 5000, estimate_mod: -6.32, error_mod: 1.85 }} />);
  expect(screen.getByText('· ΔOD -6.32 mOD')).toBeInTheDocument();
  expect(screen.getByText('· Maximum pointwise error 1.85 mOD')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Stop pairs' }));
  expect(props.onStop).toHaveBeenCalled();
});

test('direct precision displays the per-delay error envelope and maximum SE in a pop-up', () => {
  render(<VD2PairedCapture {...props} directTango run={{ active: true, status: 'acquiring',
    mode: 'precision', band, job_id: 'job', target_mod: 1, error_mod: 1.4,
    pairs_recorded: 180, pair_limit: null, kinetics: { time: [0, 1], od_mod: [0.25, 0.4], se_mod: [0.2, 1.4] } }} />);
  expect(screen.getByRole('dialog', { name: 'Live OD kinetics' })).toBeInTheDocument();
  expect(screen.getByLabelText('Pointwise standard error')).toBeInTheDocument();
  expect(screen.getByText('Max SE 1.40 mOD')).toBeInTheDocument();
  expect(screen.getByPlaceholderText('No frame limit')).toHaveValue(null);
});

test('missing Bruit closes the streak shutter and resumes after the new reference is verified', async () => {
  const onBruit = jest.fn();
  const previous = { job_id: 'older', phase: 'BASE', status: 'completed' };
  const run = { job_id: 'paired', sample_name: 'sample', status: 'bruit_required', active: false };
  fetchVd2.mockResolvedValue({ ok: true, json: async () => ({ success: true, paired: { active: true } }) });
  const view = render(<VD2PairedCapture {...props} run={run} protocol={previous} onBruit={onBruit} />);
  fireEvent.click(screen.getByRole('button', { name: 'Record Bruit' }));
  await waitFor(() => expect(onBruit).toHaveBeenCalled());
  expect(fetchVd2.mock.calls.at(-1)[0]).toMatch(/parameter\/streak_shutter$/);
  view.rerender(<VD2PairedCapture {...props} run={run} onBruit={onBruit}
    protocol={{ job_id: 'new-bruit', phase: 'BRUIT', sample_name: 'sample', status: 'completed' }} />);
  fireEvent.click(screen.getByRole('button', { name: 'Open shutters and continue' }));
  await waitFor(() => expect(fetchVd2.mock.calls.at(-1)[0]).toMatch(/paired\/start$/));
  expect(fetchVd2.mock.calls.at(-2)[0]).toMatch(/alignment\/open-shutters$/);
});


test('both selections are required to start a measurement', () => {
  const view = render(<VD2PairedCapture {...props} referenceConfirmed={false} />);
  expect(screen.getByRole('button', { name: 'Measurement' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled();
  expect(screen.getByLabelText('Bandwidth (nm)')).toBeDisabled();
  expect(screen.getByLabelText('Lamp reference rows')).toBeEnabled();

  view.rerender(<VD2PairedCapture {...props} correctionFixed={false} />);
  expect(screen.getByRole('button', { name: 'Measurement' })).toBeDisabled();
  expect(screen.getByLabelText('Bandwidth (nm)')).toBeEnabled();
  expect(screen.getByLabelText('Lamp reference rows')).toBeDisabled();
});

test('correction defaults to 120 nm within the measured columns on a descending axis', () => {
  const calibration = {
    wavelengths: [640, 590, 570, 490, 450, 420], height: 40,
    spectral_calibration: ['hg-r2', [1, 4]],
  };
  const result = pairedSpectralRegion(calibration, DEFAULT_PAIRED_CORRECTION);
  expect(result.band).toEqual({ center_nm: 520, half_width_nm: 60, monitor_rows: 30 });
  expect(result.bounds).toMatchObject({ x0: 2, x1: 3 });
  expect(pairedSpectralRegion(calibration, { ...DEFAULT_PAIRED_CORRECTION, bandwidth: '150' }).band).toBeUndefined();
  const invalidRows = pairedSpectralRegion(calibration, { ...DEFAULT_PAIRED_CORRECTION, monitorRows: '40' });
  expect(invalidRows.band).toBeUndefined();
  expect(invalidRows.bounds).toEqual(result.bounds);
  expect(invalidRows.referenceRows).toBeNull();
});
