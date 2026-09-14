import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LaserPointingClients from './LaserPointingClients';

jest.mock('./components/LaserPointingController', () => ({ deviceName }) => (
  <div data-testid="laser-controller">{deviceName}</div>
));

describe('LaserPointing device selection', () => {
  test('does not load controllers until the operator selects them', () => {
    render(
      <MemoryRouter>
        <LaserPointingClients deviceOverride={[
          'elyse/laserpointing/LaserPointing2',
          'elyse/laserpointing/LaserPointing1',
        ]} />
      </MemoryRouter>
    );

    expect(screen.queryAllByTestId('laser-controller')).toHaveLength(0);
    expect(screen.getByRole('button', { name: 'Load Selected (0)' })).toBeDisabled();

    fireEvent.click(screen.getByRole('checkbox', { name: 'elyse/laserpointing/LaserPointing2' }));
    fireEvent.click(screen.getByRole('button', { name: 'Load Selected (1)' }));

    expect(screen.getAllByTestId('laser-controller')).toHaveLength(1);
    expect(screen.getByTestId('laser-controller')).toHaveTextContent(
      'elyse/laserpointing/LaserPointing2'
    );
  });

  test('supports loading multiple selected controllers', () => {
    render(
      <MemoryRouter>
        <LaserPointingClients deviceOverride={['laser/one', 'laser/two']} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Select All' }));
    fireEvent.click(screen.getByRole('button', { name: 'Load Selected (2)' }));

    const controllers = screen.getAllByTestId('laser-controller');
    expect(controllers).toHaveLength(2);
    expect(controllers.map((controller) => controller.textContent)).toEqual([
      'laser/one',
      'laser/two',
    ]);
  });
});
