const INSTRUMENT_NAMES = {
  ANDOR_KYMERA1: 'Kymera',
  DG645: 'DG645',
  DS_OWIS_PS90_IP: 'OWIS',
};

export function preparationPhase(phase) {
  if (!phase) return 'Checking equipment…';
  if (phase.startsWith('Initializing Kymera SDK')) return 'Initializing Kymera — please wait…';
  const recovery = phase.match(/^([^:]+): Attempting device recovery command ([^;]+)(?:; server retained)?$/);
  if (!recovery) return phase;
  const device = recovery[1].split('/').pop();
  const instrument = INSTRUMENT_NAMES[device] || device;
  return `${recovery[2] === 'turn_on' ? 'Initializing' : 'Recovering'} ${instrument} — please wait…`;
}

function duration(seconds) {
  const elapsed = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;
}

export function preparationElapsed(job, serverNow) {
  const start = Number.isFinite(job.created_at) ? job.created_at : serverNow;
  const phases = (job.events || []).filter(event => event.job_id === job.job_id
    && event.kind === 'progress' && event.message === job.phase && Number.isFinite(event.timestamp));
  const phaseStart = phases.length ? phases[phases.length - 1].timestamp
    : Number.isFinite(job.updated_at) ? job.updated_at : start;
  return `Stage ${duration(serverNow - phaseStart)} · Total ${duration(serverNow - start)}`;
}
