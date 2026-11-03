import unittest
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from tools.elyse_cooling_alert import CoolingAlert, CIRCUITS
from legacy.xp_acq_control.elyse_agent.cooling_safety import CIRCUITS as HARDWARE_SIGNALS


def banks(general=True, canon=False, section=False, sequence=1, session='owner',
          chauffage=True, regulation=True):
    eps, c3 = [False] * 77, [False] * 56
    eps[8], c3[0], c3[6] = general, canon, section
    eps[14], eps[2] = chauffage, regulation
    return {name: dict(data=data, age_seconds=0.1, stale=False,
                       error=dict(status=False, code=0), session_id=session, sequence=sequence)
            for name, data in (('EPS', eps), ('C3_IN_DIO96', c3))}


class CoolingAlertTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows byte-range lock semantics')
    def test_second_instance_exits_without_tk_tango_or_duplicate_audio(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as directory:
            with (Path(directory) / 'monitor.lock').open('w+b') as owner:
                owner.write(b'0')
                owner.flush()
                owner.seek(0)
                msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)
                script = Path(__file__).resolve().parents[2] / 'tools/elyse_cooling_alert.py'
                child = subprocess.run([sys.executable, str(script), '--directory', directory],
                                       capture_output=True, timeout=5)
                self.assertEqual(child.returncode, 0, child.stderr.decode(errors='replace'))

    def test_polarity_matches_saved_supervision_indications(self):
        for name, index in CIRCUITS.items():
            self.assertEqual(HARDWARE_SIGNALS[name][0], ('C3_IN_DIO96', index, True, '220V'))

    def test_general_alone_or_only_one_required_stage_never_arms_or_sounds(self):
        for chauffage, regulation in ((False, False), (False, True), (True, False)):
            p = CoolingAlert()
            s = p.update(banks(canon=True, section=True, chauffage=chauffage,
                               regulation=regulation), now=0)
            self.assertFalse(s['active'])
            self.assertFalse(s['operating'])
            self.assertEqual(s['armed'], [])
            self.assertEqual(s['cold_red'], ['CANON', 'SECTION'])
            self.assertFalse(p.update(error='timeout', now=1)['active'])

    def test_red_already_present_when_both_stages_on_requires_attention(self):
        p = CoolingAlert()
        s = p.update(banks(canon=True, section=True), now=0)
        self.assertTrue(s['operating'])
        self.assertEqual(s['faults'], ['CANON', 'SECTION'])

    def test_both_losses_alarm_immediately_and_escalation_has_new_episode(self):
        p = CoolingAlert()
        p.update(banks(), now=0)
        first = p.update(banks(canon=True, sequence=2), now=0.5)
        self.assertEqual(first['faults'], ['CANON'])
        second = p.update(banks(canon=True, section=True, sequence=3), now=1)
        self.assertEqual(second['faults'], ['CANON', 'SECTION'])
        self.assertNotEqual(first['episode'], second['episode'])
        self.assertEqual(second['episode'], p.update(banks(canon=True, section=True, sequence=4), now=1.5)['episode'])

    def test_stale_bad_schema_and_faulted_reads_cannot_clear_alarm(self):
        for mutate in (lambda b: b.update(stale=True), lambda b: b.update(age_seconds=2),
                       lambda b: b.update(error=dict(status=True, code=-1)),
                       lambda b: b.update(data=[False]), lambda b: b.update(age_seconds=float('nan'))):
            p = CoolingAlert()
            p.update(banks(), now=0)
            p.update(banks(canon=True, sequence=2), now=0.5)
            invalid = banks(sequence=3)
            mutate(invalid['C3_IN_DIO96'])
            s = p.update(invalid, now=3)
            self.assertEqual(s['faults'], ['CANON'])
            self.assertIn('TELEMETRY', s['reasons'])

    def test_recovery_requires_two_seconds_of_fresh_progressing_data(self):
        p = CoolingAlert()
        p.update(banks(), now=0)
        p.update(banks(canon=True, sequence=2), now=0.5)
        self.assertTrue(p.update(banks(sequence=3), now=1)['active'])
        self.assertTrue(p.update(banks(sequence=4), now=2)['active'])
        self.assertFalse(p.update(banks(sequence=5), now=3)['active'])
        self.assertTrue(p.update(banks(canon=True, sequence=6), now=3.5)['active'])

    def test_frozen_age_zero_replies_do_not_prove_health_or_recovery(self):
        p = CoolingAlert()
        sample = banks()
        p.update(sample, now=0)
        self.assertFalse(p.update(sample, now=1.99)['active'])
        self.assertEqual(p.update(sample, now=2)['reasons'], ['TELEMETRY'])

    def test_each_fresh_stage_off_clears_alarm_but_stale_off_does_not(self):
        for off in ({'chauffage': False}, {'regulation': False}):
            p = CoolingAlert()
            p.update(banks(), now=0)
            self.assertTrue(p.update(banks(canon=True, sequence=2), now=0.5)['active'])
            stale = banks(canon=True, sequence=3, **off)
            stale['EPS']['stale'] = True
            self.assertTrue(p.update(stale, now=1)['active'])
            s = p.update(banks(canon=True, sequence=4, **off), now=1.5)
            self.assertFalse(s['active'])
            self.assertEqual(s['armed'], [])

    def test_old_general_only_saved_state_is_not_new_policy_arming(self):
        p = CoolingAlert(dict(general=True, armed=['CANON'], faults=['CANON']))
        self.assertFalse(p.update(error='no initial read', now=0)['active'])
        s = p.update(banks(canon=True, chauffage=False, regulation=False), now=0.5)
        self.assertEqual(s['faults'], [])

    def test_restart_retains_armed_state_and_fault_not_silence(self):
        p = CoolingAlert()
        saved = p.update(banks(), now=0)
        new = CoolingAlert(saved)
        self.assertEqual(new.update(banks(canon=True, sequence=2), now=0)['faults'], ['CANON'])

    def test_mixed_owner_sessions_are_unknown_not_normal(self):
        p = CoolingAlert()
        mixed = banks()
        mixed['C3_IN_DIO96']['session_id'] = 'prior_owner'
        self.assertEqual(p.update(mixed, now=0)['reasons'], ['TELEMETRY'])

    def test_transport_recovery_after_outage_keeps_prior_fault(self):
        p = CoolingAlert()
        p.update(banks(), now=0)
        p.update(banks(canon=True, sequence=2), now=0.5)
        p.update(error='timeout', now=1)
        s = p.update(banks(canon=True, sequence=3), now=1.5)
        self.assertEqual(s['reasons'], ['CANON'])


if __name__ == '__main__':
    unittest.main()
