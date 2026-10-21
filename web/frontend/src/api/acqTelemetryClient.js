// Read-only standard-bank endpoint. No direct XP or device command path.
export const acqTelemetryClient = Object.freeze({
  async telemetry(signal) {
    const response = await fetch('/api/elyse/acquisition/telemetry', {
      method: 'GET', credentials: 'include', cache: 'no-store', signal,
    });
    const value = await response.json();
    if (!response.ok || value.schema_version !== 1 || !Array.isArray(value.expected_banks)) {
      throw new Error(value.error || 'Contrat de télémétrie Acquisition incompatible.');
    }
    return value;
  },
});
