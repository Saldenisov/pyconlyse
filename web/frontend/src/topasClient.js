import { fetchWithHardwareApproval } from './api/csrfRequest';

export const TOPAS_DEVICE = 'manip/laser/topas_t21082';
const base = `/api/device/${encodeURIComponent(TOPAS_DEVICE)}`;

async function payload(response) {
  const data = await response.json();
  if (!response.ok || data.success === false) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

export async function readTopas(signal) {
  const data = await payload(await fetch(`${base}/attribute/snapshot_json`, {
    credentials: 'include', cache: 'no-store', signal,
  }));
  const snapshot = JSON.parse(data.value);
  if (typeof snapshot.fresh !== 'boolean') throw new Error('Invalid TOPAS status');
  return snapshot;
}

export async function sendTopas(command, args = []) {
  const requestId = Array.from(crypto.getRandomValues(new Uint8Array(16)), v => v.toString(16).padStart(2, '0')).join('');
  return payload(await fetchWithHardwareApproval(`${base}/command/SubmitOperation`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ args: JSON.stringify({ request_id: requestId, command, arguments: args }) }),
  }));
}

export async function acknowledgeTopasError() {
  return payload(await fetchWithHardwareApproval(`${base}/command/ClearError`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ args: null }),
  }));
}
