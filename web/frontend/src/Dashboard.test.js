import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Dashboard from './Dashboard';

const originalFetch = global.fetch;

const jsonResponse = (payload) => ({
  ok: true,
  status: 200,
  json: jest.fn().mockResolvedValue(payload),
});

describe('Dashboard server actions', () => {
  beforeEach(() => {
    document.cookie = 'csrf_access_token=server%20token; path=/';
    global.fetch = jest.fn((url) => {
      if (url === '/api/tango_status') {
        return Promise.resolve(jsonResponse({
          mysql_status: true,
          tango_host: 'stub.invalid:1',
          starters: [],
        }));
      }
      if (url.startsWith('/api/devices?')) {
        return Promise.resolve(jsonResponse({
          devices: [{
            name: 'sys/test/1',
            server: 'FakeServer/one',
            class: 'FakeDevice',
            available: true,
            state: 'ON',
          }],
        }));
      }
      if (url === '/api/server/control') {
        return Promise.resolve(jsonResponse({
          success: true,
          server_name: 'FakeServer/one',
          starter: 'tango/admin/fake',
        }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
  });

  afterEach(() => {
    if (originalFetch === undefined) {
      delete global.fetch;
    } else {
      global.fetch = originalFetch;
    }
    document.cookie = 'csrf_access_token=; Max-Age=0; path=/';
  });

  test('sends only the bound server action fields with CSRF protection', async () => {
    render(<Dashboard />);

    fireEvent.click(await screen.findByRole('button', { name: 'Start' }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/server/control', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-TOKEN': 'server token',
        },
        body: JSON.stringify({
          action: 'start',
          server_name: 'FakeServer/one',
        }),
      });
    });
  });
});
