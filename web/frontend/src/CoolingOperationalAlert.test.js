import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CoolingOperationalAlert, { newCoolingWatch, observeCooling } from './CoolingOperationalAlert';

function sample({ general = true, canon = false, section = false, sequence = 1,
  chauffage = true, regulation = true } = {}) {
  const eps = Array(77).fill(false); eps[8] = general; eps[14] = chauffage; eps[2] = regulation;
  const c3 = Array(56).fill(false); c3[0] = canon; c3[6] = section;
  const bank = (name, data) => ({ data, age_seconds: 0.1, stale: false, sequence, session_id: 'owner',
    error: { status: false, code: 0 }, lv_type: { type: 'Cluster', name,
      fields: data.map(() => ({ type: 'Boolean' })) } });
  return { elapsed: 0, failure: '', payload: { snapshot: { publications: {
    EPS: bank('EPS', eps), C3_IN_DIO96: bank('C3_IN_DIO96', c3),
  } } } };
}

test('General alone or only one required stage never arms or sounds', () => {
  [[false, false], [false, true], [true, false]].forEach(([chauffage, regulation]) => {
    const w = newCoolingWatch();
    const result = observeCooling(w, sample({ canon: true, section: true, chauffage, regulation }), 0);
    expect(result).toEqual({ faults: [], monitoringLost: false });
    expect(w.armed.size).toBe(0);
    expect(observeCooling(w, { failure: 'timeout' }, 1).monitoringLost).toBe(false);
  });
});

test('both stages ON alarms even for initially red input; either stage OFF disarms', () => {
  const w = newCoolingWatch();
  expect(observeCooling(w, sample({ canon: true, section: true }), 0).faults).toEqual(['CANON', 'SECTION']);
  expect(observeCooling(w, sample({ chauffage: false, sequence: 2 }), 0.5).faults).toEqual([]);
  expect(observeCooling(w, sample({ canon: true, sequence: 3 }), 1).faults).toEqual(['CANON']);
  expect(observeCooling(w, sample({ regulation: false, sequence: 4 }), 1.5).faults).toEqual([]);
  expect(w.armed.size).toBe(0);
});

test('stale replies retain fault and report lost monitoring; recovery requires 2 s', () => {
  const w = newCoolingWatch();
  observeCooling(w, sample(), 0);
  observeCooling(w, sample({ canon: true, sequence: 2 }), 0.5);
  expect(observeCooling(w, { ...sample(), failure: 'timeout' }, 1)).toEqual({ faults: ['CANON'], monitoringLost: true });
  expect(observeCooling(w, sample({ sequence: 3 }), 2).faults).toEqual(['CANON']);
  expect(observeCooling(w, sample({ sequence: 4 }), 3).faults).toEqual(['CANON']);
  expect(observeCooling(w, sample({ sequence: 5 }), 4).faults).toEqual([]);
});

test('frozen sequence with fake age zero and mixed owner replies are not healthy', () => {
  const w = newCoolingWatch();
  const s = sample();
  observeCooling(w, s, 0);
  expect(observeCooling(w, s, 2).monitoringLost).toBe(true);
  const mixed = sample({ sequence: 2 });
  mixed.payload.snapshot.publications.C3_IN_DIO96.session_id = 'old';
  expect(observeCooling(w, mixed, 2.5).monitoringLost).toBe(true);
});

test('global alert offers details without a hardware dispatch or dismiss action', () => {
  const open = jest.fn();
  const { rerender } = render(<CoolingOperationalAlert telemetry={sample()} onOpenJournal={open} />);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  rerender(<CoolingOperationalAlert telemetry={sample({ canon: true, sequence: 2 })} onOpenJournal={open} />);
  expect(screen.getByRole('alert')).toHaveTextContent('CANON');
  expect(screen.getByRole('alert')).toHaveTextContent('Vérifier immédiatement le moteur');
  fireEvent.click(screen.getByRole('button', { name: 'Voir les détails' }));
  expect(open).toHaveBeenCalledTimes(1);
});
