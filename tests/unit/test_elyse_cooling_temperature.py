import unittest
from tools.elyse_cooling_temperature import TemperatureWatch, load_policy
from tools.elyse_cooling_alert import CoolingAlert
from tests.unit.test_elyse_cooling_alert import banks


def readings(t, canon=21.3, section=28.3, canon_sp=21.1, section_sp=28.2, session='owner'):
    return {'CANON': (canon, canon_sp, (session, t, t)), 'SECTION': (section, section_sp, (session, t, t))}


class TemperatureTests(unittest.TestCase):
    def warm(self, watch):
        for t in range(31):
            watch.update(True, readings(t), t)

    def test_stable_offset_below_target_rise_and_transient_spike_do_not_warn(self):
        for scenario in ('offset', 'below_target', 'spike'):
            watch = TemperatureWatch()
            for t in range(180):
                value = 22.5 if scenario == 'offset' else 20 + min(t, 60) / 60 if scenario == 'below_target' else 22.5 if t == 60 else 21.3
                self.assertEqual(watch.update(True, readings(t, canon=value), t)['warnings'], [])

    def test_rising_deviation_warns_after_persistence_independently_for_both(self):
        w = TemperatureWatch(); self.warm(w)
        for t in range(31, 46):
            self.assertEqual(w.update(True, readings(t, canon=22.5, section=29.6), t)['warnings'], [])
        result = w.update(True, readings(46, canon=22.5, section=29.6), 46)
        self.assertEqual([x['circuit'] for x in result['warnings']], ['CANON', 'SECTION'])
        self.assertAlmostEqual(result['warnings'][0]['deviation_c'], 1.4)

    def test_pending_interval_cannot_bridge_unknown_or_long_gap(self):
        for missing in ('unknown', 'gap'):
            w = TemperatureWatch(); self.warm(w)
            w.update(True, readings(31, canon=22.5), 31)
            if missing == 'unknown': w.update(True, {}, 35)
            self.assertEqual(w.update(True, readings(50, canon=22.5), 50)['warnings'], [])
            for t in range(51, 65):
                self.assertEqual(w.update(True, readings(t, canon=22.5), t)['warnings'], [])
            self.assertEqual(len(w.update(True, readings(65, canon=22.5), 65)['warnings']), 1)

    def test_setpoint_change_and_source_change_restart_comparison(self):
        for change in ('setpoint', 'session'):
            w = TemperatureWatch(); self.warm(w)
            for t in range(31, 70):
                args = {'canon_sp': 22.3} if change == 'setpoint' else {'session': 'new'}
                self.assertEqual(w.update(True, readings(t, canon=22.5, **args), t)['warnings'], [])

    def test_fresh_recovery_requires_30_seconds_and_unknown_cannot_clear(self):
        w = TemperatureWatch(); self.warm(w)
        for t in range(31, 47): r = w.update(True, readings(t, canon=22.5), t)
        self.assertEqual(len(r['warnings']), 1)
        self.assertEqual(w.update(True, {}, 47)['warnings'][0]['quality'], 'UNKNOWN')
        for t in range(48, 78):
            self.assertEqual(len(w.update(True, readings(t), t)['warnings']), 1)
        self.assertEqual(w.update(True, readings(78), 78)['warnings'], [])

    def test_scope_off_disarms_and_restart_retains_existing_warning(self):
        saved = dict(circuit='CANON', temperature_c=22.5, setpoint_c=21.1, deviation_c=1.4, rise_c=1.2)
        w = TemperatureWatch(saved=[saved])
        self.assertEqual(len(w.update(None, {}, 0)['warnings']), 1)
        self.assertEqual(w.update(False, {}, 1)['warnings'], [])

    def test_default_policy_is_explicit_and_shared_with_web(self):
        p = load_policy()
        self.assertEqual((p['excess_c'], p['rise_c'], p['window_seconds'], p['persistence_seconds']), (1, .5, 120, 15))

    def test_full_monitor_warns_with_green_220v_and_actual_numeric_banks(self):
        p = CoolingAlert()
        for t in range(47):
            b = banks(sequence=t + 1)
            c1, c8 = [0.] * 64, [0.] * 10
            c1[0], c1[8], c8[1], c8[2] = 21.3 if t <= 30 else 22.5, 28.3, 21.1, 28.2
            for name, data in (('C1NI6071E', c1), ('C8NI6703', c8)):
                b[name] = dict(b['EPS'], data=data)
            result = p.update(b, now=t)
        self.assertEqual(result['faults'], [])
        self.assertEqual(result['severity'], 'WARNING')
        self.assertEqual(result['reasons'], ['TEMPERATURE:CANON'])
        self.assertEqual(result['temperature_alerts'][0]['setpoint_c'], 21.1)


if __name__ == '__main__': unittest.main()
