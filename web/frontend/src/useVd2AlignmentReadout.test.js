import { act, render, screen, waitFor } from '@testing-library/react';
import { useVd2AlignmentReadout } from './useVd2AlignmentReadout';

const region = { wavelengthMin: 500, wavelengthMax: 700, topPercent: 0, bottomPercent: 20 };
const first = { baseline: [0, 1], signal: [2, 3] };
const second = { baseline: [0, 1], signal: [3, 4] };

function View({name, windows, frameId = 'frame'}) {
  const {result, error} = useVd2AlignmentReadout(frameId, 'same ROI', region, windows);
  return <output aria-label={name}>{result?.payload.summary.mean ?? (error || 'pending')}</output>;
}

const reply = (mean, frameId = 'frame') => ({ok: true, json: async () => ({
  success: true, version: 1, profile: {frameId}, summary: {mean},
})});

test('same-origin windows request their own zones and a late reply cannot override an edit', async () => {
  const fetchBefore = global.fetch;
  const pending = [];
  global.fetch = jest.fn((url, options) => new Promise(resolve => pending.push({
    resolve, signal: options.signal, selection: JSON.parse(new URL(url, 'http://localhost').searchParams.get('selection')),
  })));
  try {
    const view = render(<><View name="first" windows={first}/><View name="second" windows={first}/></>);
    await waitFor(() => expect(pending).toHaveLength(2));
    view.rerender(<><View name="first" windows={first}/><View name="second" windows={second}/></>);
    await waitFor(() => expect(pending).toHaveLength(3));
    expect(pending.map(p => p.selection.windows)).toEqual([first, first, second]);
    expect(pending[1].signal.aborted).toBe(true);
    await act(async () => { pending[0].resolve(reply(15)); pending[2].resolve(reply(0)); });
    expect(screen.getByLabelText('first')).toHaveTextContent('15');
    expect(screen.getByLabelText('second')).toHaveTextContent('0');
    await act(async () => { pending[1].resolve(reply(15)); });
    expect(screen.getByLabelText('second')).toHaveTextContent('0');
  } finally { global.fetch = fetchBefore; }
});
