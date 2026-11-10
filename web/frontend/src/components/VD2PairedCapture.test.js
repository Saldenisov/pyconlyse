import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import VD2PairedCapture from './VD2PairedCapture';
import { fetchVd2 } from '../PumpProbeVD2.API_BASE';

jest.mock('../PumpProbeVD2.API_BASE', () => ({
  ...jest.requireActual('../PumpProbeVD2.API_BASE'), fetchVd2: jest.fn(),
}));

const props = {
  available: true,
  settings: { outputRoot: 'E:/DATA_VD2/test', runName: 'sample', reuseBruit: 'latest' },
  preview: { width: 10, height: 20 },
  onUpdate: jest.fn(), onStop: jest.fn(),
};

test('precision mode sends the selected detector ROI and operator phase', async () => {
  fetchVd2.mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, paired: { active: true } }) });
  const view = render(<VD2PairedCapture {...props} />);
  fireEvent.change(screen.getByLabelText('Stop condition'), { target: { value: 'precision' } });
  expect(screen.getByRole('button', { name: 'Measure pairs' })).toBeDisabled();
  view.rerender(<VD2PairedCapture {...props} roi={{ x0: 8, x1: 2, y0: 4, y1: 8 }} />);
  fireEvent.click(screen.getByLabelText('First frame with electrons'));
  fireEvent.click(screen.getByRole('button', { name: 'Measure pairs' }));
  await waitFor(() => expect(props.onUpdate).toHaveBeenCalledWith({ active: true }));
  const [url, options] = fetchVd2.mock.calls.at(-1);
  expect(url).toBe('/api/pump-probe-vd2/paired/start');
  expect(JSON.parse(options.body)).toMatchObject({
    first_map_with_electrons: false, mode: 'precision', target_mod: 2,
    roi: { x0: 2, x1: 8, y0: 4, y1: 8, width: 10, height: 20 },
  });
});

test('shows signed OD and permits stopping the recording', () => {
  render(<VD2PairedCapture {...props} run={{ active: true, status: 'acquiring', mode: 'precision',
    job_id: 'job', target_mod: 2, first_map_with_electrons: true, trigger_source: 'external_rising',
    pairs_recorded: 200, pair_limit: 5000, estimate_mod: -6.32, error_mod: 1.85 }} />);
  expect(screen.getByText('· ΔOD -6.32 mOD')).toBeInTheDocument();
  expect(screen.getByText('· ROI error 1.85 mOD')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Stop pairs' }));
  expect(props.onStop).toHaveBeenCalled();
});
