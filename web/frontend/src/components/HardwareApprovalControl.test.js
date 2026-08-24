import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import HardwareApprovalControl from './HardwareApprovalControl';
import {
  clearHardwareApprovalNonce,
  fetchWithHardwareApproval,
  getHardwareApprovalNonce,
} from '../api/csrfRequest';

const originalFetch = global.fetch;

describe('HardwareApprovalControl', () => {
  beforeEach(() => {
    clearHardwareApprovalNonce();
  });

  afterEach(() => {
    cleanup();
    clearHardwareApprovalNonce();
    if (originalFetch === undefined) {
      delete global.fetch;
    } else {
      global.fetch = originalFetch;
    }
  });

  test('arms one exact operator-provided nonce and clears the input', () => {
    render(<HardwareApprovalControl />);
    const nonce = 'd'.repeat(64);

    fireEvent.change(screen.getByLabelText('Hardware approval nonce'), { target: { value: nonce } });
    fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));

    expect(getHardwareApprovalNonce()).toBe(nonce);
    expect(screen.getByLabelText('Hardware approval nonce')).toHaveValue('');
    expect(screen.getByText('Hardware approval armed for one mutation attempt.')).toBeInTheDocument();
  });

  test('invalid replacement clears a previously armed nonce', () => {
    render(<HardwareApprovalControl />);
    const input = screen.getByLabelText('Hardware approval nonce');
    fireEvent.change(input, { target: { value: 'e'.repeat(64) } });
    fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));
    fireEvent.change(input, { target: { value: 'INVALID' } });
    fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));

    expect(getHardwareApprovalNonce()).toBeNull();
    expect(screen.getByText(/Invalid approval nonce/)).toBeInTheDocument();
  });

  test.each([
    ['resolves', () => Promise.resolve({ ok: true })],
    ['rejects', () => Promise.reject(new Error('fetch rejected'))],
    ['throws', () => { throw new Error('fetch threw'); }],
  ])('shows consumed after a mutation attempt that %s', async (_label, implementation) => {
    global.fetch = jest.fn(implementation);
    render(<HardwareApprovalControl />);
    fireEvent.change(screen.getByLabelText('Hardware approval nonce'), {
      target: { value: 'f'.repeat(64) },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Arm one mutation' }));

    await act(async () => {
      try {
        await fetchWithHardwareApproval('/api/device/test/command/start', { method: 'POST' });
      } catch (_error) {
        // Consumption is required for rejected and thrown fetch attempts.
      }
    });

    expect(getHardwareApprovalNonce()).toBeNull();
    expect(screen.getByText('Hardware approval consumed by a mutation attempt.')).toBeInTheDocument();
  });
});
