import { buildTreatmentSessionId, getBrowserNamespace } from './DataWindowVD2';

const COOKIE = 'pyconlyse_treatment_browser_namespace';
const STORAGE = 'pyconlyse_treatment_namespace';

afterEach(() => {
  jest.restoreAllMocks();
  window.localStorage.removeItem(STORAGE);
  document.cookie = `${COOKIE}=; Path=/; Max-Age=0`;
});

test('keeps browser treatment namespace across reload when localStorage is unavailable', () => {
  window.localStorage.removeItem(STORAGE);
  document.cookie = `${COOKIE}=stable-browser-namespace; Path=/; SameSite=Lax`;
  jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('storage disabled');
  });

  expect(getBrowserNamespace()).toBe('stable-browser-namespace');
  expect(getBrowserNamespace()).toBe('stable-browser-namespace');
});

test('writes a cookie fallback for an existing localStorage namespace', () => {
  window.localStorage.setItem(STORAGE, 'stored-browser-namespace');

  expect(getBrowserNamespace()).toBe('stored-browser-namespace');
  expect(document.cookie).toContain(`${COOKIE}=stored-browser-namespace`);
});

test('new workspaces use separate sessions and preserve the original main session', () => {
  window.localStorage.setItem(STORAGE, 'stored-browser-namespace');
  expect(buildTreatmentSessionId('VD2')).toBe('browser:stored-browser-namespace:profile:vd2');
  expect(buildTreatmentSessionId('VD2', 'ws-one')).toBe('browser:stored-browser-namespace:profile:vd2:workspace:ws-one');
  expect(buildTreatmentSessionId('VD2', 'ws-two')).not.toBe(buildTreatmentSessionId('VD2', 'ws-one'));
});

test('separate windows in one browser never share the same treatment session',()=>{
  window.localStorage.setItem(STORAGE,'stored-browser-namespace');
  const first=buildTreatmentSessionId('VD2','main','window-one-1234');
  const second=buildTreatmentSessionId('VD2','main','window-two-1234');
  expect(first).not.toBe(second);
  expect(first).toBe(buildTreatmentSessionId('VD2','main','window-one-1234'));
  expect(first).toContain(':window:window-one-1234:profile:vd2');
});

test('uses backend session cookie when browser storage has no namespace', () => {
  window.localStorage.removeItem(STORAGE);
  document.cookie = `${COOKIE}=; Path=/; Max-Age=0`;
  jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('storage disabled');
  });

  expect(getBrowserNamespace()).toBe('');
});
