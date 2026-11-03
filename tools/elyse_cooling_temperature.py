"""Read-only temperature-deviation warning, not a physical cooling-trip diagnosis."""
from collections import deque
import json
import math
from pathlib import Path


def load_policy():
    local = Path(__file__).with_name('coolingTemperaturePolicy.json')
    path = local if local.is_file() else Path(__file__).resolve().parents[1] / 'web/frontend/src/coolingTemperaturePolicy.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    expected = {'schema_version', 'excess_c', 'rise_c', 'window_seconds', 'minimum_span_seconds',
                'persistence_seconds', 'clear_margin_c', 'clear_seconds', 'setpoint_change_c'}
    if (set(value) != expected or value['schema_version'] != 1
            or any(type(v) not in (float, int) or not math.isfinite(v) or v <= 0 for v in value.values())
            or value['clear_margin_c'] >= value['excess_c']
            or value['minimum_span_seconds'] >= value['window_seconds']):
        raise ValueError('Invalid temperature warning policy')
    return value


class TemperatureWatch:
    def __init__(self, policy=None, saved=None):
        self.policy = load_policy() if policy is None else policy
        self.states = {name: dict(samples=deque(), setpoint=None, pending=None, clearing=None,
                                  active=False, detail={}, last_key=None, last_time=None)
                       for name in ('CANON', 'SECTION')}
        for item in saved or []:
            if isinstance(item, dict) and item.get('circuit') in self.states:
                state = self.states[item['circuit']]
                state['active'], state['detail'] = True, dict(item)

    def reset(self, name):
        self.states[name] = dict(samples=deque(), setpoint=None, pending=None, clearing=None,
                                 active=False, detail={}, last_key=None, last_time=None)

    def update(self, operating, readings, now):
        p, qualities = self.policy, {}
        for name, state in list(self.states.items()):
            if operating is False:
                self.reset(name)
                qualities[name] = 'DISARMED'
                continue
            reading = readings.get(name) if isinstance(readings, dict) else None
            if operating is not True or reading is None:
                state['pending'], state['clearing'] = None, None
                qualities[name] = 'UNKNOWN'
                continue
            temperature, setpoint, key = reading
            if (type(temperature) not in (float, int) or not math.isfinite(temperature)
                    or type(setpoint) not in (float, int) or not math.isfinite(setpoint)):
                state['pending'], state['clearing'] = None, None
                qualities[name] = 'UNKNOWN'
                continue
            qualities[name] = 'FRESH'
            if ((state['setpoint'] is not None and abs(setpoint - state['setpoint']) >= p['setpoint_change_c'])
                    or state['last_key'] is not None and key[0] != state['last_key'][0]):
                # An intentional new target starts a new comparison epoch.
                self.reset(name)
                state = self.states[name]
            state['setpoint'] = setpoint
            error = temperature - setpoint
            samples = state['samples']
            while samples and samples[0][0] < now - p['window_seconds']:
                samples.popleft()
            # Keep actual endpoint values, at most one per second; no averaging
            # or interpolation. Gaps cannot satisfy the persistence interval.
            if key != state['last_key'] and (not samples or now - samples[-1][0] >= 1):
                samples.append((now, error))
                state['last_key'] = key
            if state['last_time'] is not None and now - state['last_time'] > 2:
                state['pending'], state['clearing'] = None, None
            state['last_time'] = now
            earlier = [value for stamp, value in samples if now - stamp >= p['minimum_span_seconds']]
            rise = error - min(earlier) if earlier else None
            qualifies = error >= p['excess_c'] and rise is not None and rise >= p['rise_c']
            if not state['active']:
                if qualifies:
                    if state['pending'] is None:
                        state['pending'] = now
                    if now - state['pending'] >= p['persistence_seconds']:
                        state['active'] = True
                else:
                    state['pending'] = None
            if state['active']:
                if error <= p['excess_c'] - p['clear_margin_c']:
                    if state['clearing'] is None:
                        state['clearing'] = now
                    if now - state['clearing'] >= p['clear_seconds']:
                        state['active'], state['pending'], state['clearing'] = False, None, None
                else:
                    state['clearing'] = None
            state['detail'] = dict(circuit=name, temperature_c=temperature, setpoint_c=setpoint,
                                   deviation_c=error, rise_c=rise, window_seconds=p['window_seconds'])
        warnings = [dict(s['detail'], quality=qualities[name]) for name, s in self.states.items() if s['active']]
        return dict(warnings=warnings, quality=qualities, policy=dict(p))
