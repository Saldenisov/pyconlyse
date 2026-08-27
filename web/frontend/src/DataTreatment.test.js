import { fireEvent, render, screen } from '@testing-library/react';
import DataTreatment from './DataTreatment';

jest.mock('./DataWindowVD2', () => function MockDataWindow({ profile, layoutMode }) {
  const mockReact = require('react');
  const instanceId = mockReact.useRef(`instance-${Math.random()}`);
  return mockReact.createElement(
    'div',
    {
      'data-testid': 'treatment-window',
      'data-instance-id': instanceId.current,
      'data-layout-mode': layoutMode,
      'data-profile': profile,
    },
    profile
  );
});

describe('DataTreatment', () => {
  beforeEach(() => {
    window.localStorage.removeItem('pyconlyse.treatment.layoutMode');
  });

  test('defaults to Classic and keeps profile selection explicit', () => {
    render(<DataTreatment />);

    expect(screen.getByRole('heading', { name: 'Data Treatment' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Treatment workflow')).not.toBeInTheDocument();
    expect(screen.queryByText('VD2 web treatment is active.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Classic' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Studio' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-profile', 'VD2');
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-layout-mode', 'classic');
    expect(screen.getByRole('button', { name: 'VD2' })).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByRole('button', { name: 'V0 legacy' }));

    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-profile', 'V0');
    expect(screen.getByRole('button', { name: 'V0 legacy' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-layout-mode', 'classic');
  });

  test('persists layout mode and updates workspace without remounting it', () => {
    const { unmount } = render(<DataTreatment />);

    const workspace = screen.getByTestId('treatment-window');
    const instanceId = workspace.getAttribute('data-instance-id');

    fireEvent.click(screen.getByRole('button', { name: 'Studio' }));

    expect(screen.getByRole('button', { name: 'Classic' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Studio' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-layout-mode', 'studio');
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-instance-id', instanceId);
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-profile', 'VD2');
    expect(window.localStorage.getItem('pyconlyse.treatment.layoutMode')).toBe('studio');

    fireEvent.click(screen.getByRole('button', { name: 'Classic' }));
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-layout-mode', 'classic');
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-instance-id', instanceId);

    fireEvent.click(screen.getByRole('button', { name: 'Studio' }));
    unmount();
    render(<DataTreatment />);
    expect(screen.getByRole('button', { name: 'Studio' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-layout-mode', 'studio');
  });

  test('restores Studio from the persisted layout key on fresh mount', () => {
    window.localStorage.setItem('pyconlyse.treatment.layoutMode', 'studio');

    render(<DataTreatment />);

    expect(screen.getByRole('button', { name: 'Studio' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('treatment-window')).toHaveAttribute('data-layout-mode', 'studio');
  });
});
