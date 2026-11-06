import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import Elyse, { normalizeSupervisionTab } from './Elyse';

jest.mock('./components/AcquisitionVideo', () => () => <section aria-label="Caméra SuperVision test">Read-only video</section>);
jest.mock('./AcquisitionCommands', () => ({ children }) => <>{children}</>);

test('NI1409 tab mounts only the read-only viewer without replay or hardware operations', () => {
  const client = { snapshot: jest.fn().mockImplementation(() => new Promise(() => {})), replay: jest.fn() };
  const { unmount } = render(<Elyse client={client} />);
  fireEvent.click(screen.getByRole('tab', { name: 'Caméra NI1409', exact: true }));
  expect(screen.getByRole('region', { name: 'Caméra SuperVision test' })).toBeInTheDocument();
  expect(client.replay).not.toHaveBeenCalled();
  expect(normalizeSupervisionTab('ni1409')).toBe('ni1409');
  unmount();
});
