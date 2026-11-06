import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ElectronicsClients, { isElectronicsDevice } from './ElectronicsClients';

jest.mock('./components/ElectronicsController', () => ({ device }) => <div>controller:{device.name}</div>);

test('electronics discovery accepts Keysight and DG645 only', () => {
  expect(isElectronicsDevice({ name: 'manip/sync/DG645', class: 'DS_DG645' })).toBe(true);
  expect(isElectronicsDevice({ name: 'manip/awg/a', class: 'DS_KEYSIGHT_33509B' })).toBe(true);
  expect(isElectronicsDevice({ name: 'manip/V0/Cam1', class: 'DS_Basler_camera' })).toBe(false);
});

test('controllers stay unloaded until explicitly selected', () => {
  render(
    <MemoryRouter>
      <ElectronicsClients deviceOverride={[
        { name: 'manip/sync/DG645', class: 'DS_DG645' },
        { name: 'manip/awg/keysight', class: 'DS_KEYSIGHT_33509B' },
      ]} />
    </MemoryRouter>
  );
  expect(screen.queryByText('controller:manip/sync/DG645')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox', { name: /SRS DG645/i }));
  fireEvent.click(screen.getByRole('button', { name: 'Load selected (1)' }));
  expect(screen.getByText('controller:manip/sync/DG645')).toBeInTheDocument();
});
