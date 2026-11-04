"""Recovery policy fixtures; no live Tango, PostgreSQL, XP or NI access."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from tools import telemetry_recovery_watchdog as watchdog
from tools.telemetry_recovery_watchdog import normal_database_stop, normal_receiver_stop, plan


def fixture(receiver=True, postgres=True):
    return dict(paused=False, receiver=dict(alive=receiver), postgres=dict(alive=postgres))


class RecoveryPolicyTests(unittest.TestCase):
    def test_unarmed_and_pause_never_restart(self):
        self.assertEqual(plan({}, fixture(False, False), 0), [])
        self.assertEqual(plan(dict(enabled=True), dict(fixture(False, False), paused=True), 30), [])

    def test_missing_receiver_requires_second_observation_and_grace(self):
        state = dict(enabled=True)
        self.assertEqual(plan(state, fixture(False), 100), [])
        self.assertEqual(plan(state, fixture(False), 109), [])
        self.assertEqual(plan(state, fixture(False), 110), ['receiver'])
        self.assertEqual(plan(state, fixture(False), 150), [])
        self.assertEqual(plan(state, fixture(False), 170), ['receiver'])

    def test_live_receiver_is_untouched_even_when_no_data(self):
        state = dict(enabled=True)
        observed = fixture()
        observed['receiver']['quality'] = 'STALE'
        for now in [0, 60, 3600]:
            self.assertEqual(plan(state, observed, now), [])

    def test_existing_wrapper_listener_or_retained_pg_child_prevents_duplicate(self):
        state = dict(enabled=True)
        observed = fixture(False, False)
        observed['receiver']['occupied'] = True
        observed['postgres']['occupied'] = True
        for now in [0, 60, 3600]:
            self.assertEqual(plan(state, observed, now), [])

    def test_abrupt_loss_of_both_processes_recovers_only_these_two_targets(self):
        state = dict(enabled=True)
        self.assertEqual(plan(state, fixture(False, False), 0), [])
        self.assertEqual(plan(state, fixture(False, False), 60), ['receiver', 'postgres'])

    def test_normal_stop_stays_disarmed_until_explicit_rearm(self):
        state = dict(enabled=True)
        observed = fixture(False, False)
        for role in ('receiver', 'postgres'):
            observed[role]['normal_stop'] = True
        self.assertEqual(plan(state, observed, 0), [])
        self.assertEqual(plan(state, fixture(False, False), 3600), [])

    def test_reappearance_clears_loss_grace(self):
        state = dict(enabled=True)
        plan(state, fixture(False), 0)
        plan(state, fixture(), 60)
        self.assertEqual(plan(state, fixture(False), 120), [])
        self.assertEqual(plan(state, fixture(False), 180), ['receiver'])

    def test_operator_restart_rearms_observation_after_normal_stop(self):
        state = dict(enabled=True)
        observed = fixture(False)
        observed['receiver']['normal_stop'] = True
        plan(state, observed, 0)
        plan(state, fixture(), 30)
        self.assertEqual(plan(state, fixture(False), 60), [])
        self.assertEqual(plan(state, fixture(False), 120), ['receiver'])

    def test_wrapper_exit_zero_is_last_lifecycle_only(self):
        old = '==== timestamp starting DS_AcqTelemetry/everest ====\n==== timestamp exited with 0 ====\n'
        self.assertTrue(normal_receiver_stop(old))
        self.assertFalse(normal_receiver_stop(old + '==== new runner entered DS_AcqTelemetry/everest ====\n'))
        self.assertFalse(normal_receiver_stop(old.replace('with 0', 'with -1073741819')))
        self.assertFalse(normal_receiver_stop(''))

    def test_database_shutdown_does_not_mask_later_unclean_restart(self):
        log = 'LOG: database system is ready to accept connections\nLOG: database system is shut down\n'
        self.assertTrue(normal_database_stop(log))
        self.assertFalse(normal_database_stop(log + 'LOG: starting PostgreSQL 17.11\n'))
        self.assertFalse(normal_database_stop(''))

    def test_receiver_recovery_calls_only_named_starter_not_receiver_or_hardware(self):
        import tango
        with patch.object(tango, 'DeviceProxy') as proxy:
            result = watchdog.recover('receiver')
        proxy.assert_called_once_with('tango://10.20.30.202:10000/tango/admin/everest')
        proxy.return_value.command_inout.assert_called_once_with('DevStart', 'DS_AcqTelemetry/everest')
        self.assertIn('requested', result)

    def test_pg_existing_process_never_receives_start_even_if_recover_called(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base/'data').mkdir()
            (base/'data/PG_VERSION').write_text('17')
            with patch.object(watchdog, 'BASE', base), patch.object(watchdog.subprocess, 'run') as run:
                run.return_value.returncode = 0
                self.assertIn('Already running', watchdog.recover('postgres'))
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][1], 'status')

    def test_pg_start_does_not_wait_for_recovery_or_initialize_new_cluster(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base/'data').mkdir()
            (base/'logs').mkdir()
            (base/'data/PG_VERSION').write_text('17')
            with patch.object(watchdog, 'BASE', base), patch.object(watchdog.subprocess, 'run') as run:
                run.side_effect = [MagicMock(returncode=3), MagicMock(returncode=0)]
                self.assertIn('WAL recovery', watchdog.recover('postgres'))
                argv = run.call_args.args[0]
                self.assertEqual(argv[1], 'start')
                self.assertIn('-W', argv)
                self.assertNotIn('initdb', str(run.call_args_list))

    def test_unknown_pg_status_refuses_start(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base/'data').mkdir()
            (base/'data/PG_VERSION').write_text('17')
            with patch.object(watchdog, 'BASE', base), patch.object(watchdog.subprocess, 'run') as run:
                run.return_value.returncode = 1
                with self.assertRaisesRegex(RuntimeError, 'uncertain'):
                    watchdog.recover('postgres')
                self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
