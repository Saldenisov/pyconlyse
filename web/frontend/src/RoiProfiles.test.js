import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { RoiProfiles, updateRoisFromBounds } from './PumpProbeVD2';

const preview = { width: 4, height: 4, pixels_b64: btoa(String.fromCharCode(...Array.from({ length: 16 }, (_, i) => i))) };
const rois = [{ id: 'a', type: 'vertical', x0: 0, x1: 0, y0: 0, y1: 3 },
  { id: 'b', type: 'vertical', x0: 2, x1: 3, y0: 0, y1: 3 }];

test('all same-type ROI curves share axes and retain different intensities; legend selects the editable ROI', () => {
  const select = jest.fn();
  const view = render(<RoiProfiles preview={preview} rois={rois} selectedId="a" onSelect={select} />);
  const graph = screen.getByRole('img', { name: 'Kinetics dynamic profile' });
  const first = within(graph).getByRole('button', { name: 'ROI 1 kinetics' });
  const second = within(graph).getByRole('button', { name: 'ROI 2 kinetics' });
  expect(first.getAttribute('points')).not.toBe(second.getAttribute('points'));
  expect(first.getAttribute('stroke')).not.toBe(second.getAttribute('stroke'));
  fireEvent.click(within(screen.getByLabelText('Kinetics regions')).getByRole('button', { name: 'ROI 2' }));
  expect(select).toHaveBeenCalledWith('b');
  fireEvent.keyDown(second, { key: 'Enter' });
  expect(select).toHaveBeenCalledTimes(2);
  expect(screen.getByLabelText('ROI plot height')).toHaveValue('1');
  fireEvent.change(screen.getByLabelText('ROI plot height'), { target: { value: '1.5' } });
  expect(screen.getByLabelText('ROI plot height')).toHaveValue('1.5');
  view.rerender(<RoiProfiles preview={preview} rois={[rois[0]]} selectedId="a" onSelect={select} />);
  expect(screen.queryByRole('button', { name: 'ROI 2 kinetics' })).not.toBeInTheDocument();
});

test('mixed regions overlay on the matching spectrum/kinetics plot with actual pixel coordinates', () => {
  render(<RoiProfiles preview={preview} rois={[{ ...rois[0], type: 'rectangle', x1: 1 },
    { ...rois[1], type: 'horizontal' }]} selectedId="a" />);
  const graph = screen.getByRole('img', { name: 'Spectrum dynamic profile' });
  const a = within(graph).getByRole('button', { name: 'ROI 1 spectrum' });
  const b = within(graph).getByRole('button', { name: 'ROI 2 spectrum' });
  expect(Number(a.getAttribute('points').split(',')[0])).toBeLessThan(Number(b.getAttribute('points').split(',')[0]));
  expect(screen.queryByRole('button', { name: 'ROI 2 kinetics' })).not.toBeInTheDocument();
});

test('linked edits move/resize regions together, clamp edges and preserve independent edits', () => {
  const next = { x0: 1, x1: 1, y0: 0, y1: 3 };
  expect(updateRoisFromBounds(rois, 'a', next, false, 4, 4)[1]).toBe(rois[1]);
  expect(updateRoisFromBounds(rois, 'a', next, true, 4, 4)).toEqual(rois);
  expect(updateRoisFromBounds(rois, 'a', next, true, 6, 4)[1]).toMatchObject({ x0: 3, x1: 4, y0: 0, y1: 3 });
  expect(updateRoisFromBounds(rois, 'a', { ...next, x0: 0 }, true, 6, 4)[1]).toMatchObject({ x0: 2, x1: 4 });
  expect(rois[0].x0).toBe(0);
});
