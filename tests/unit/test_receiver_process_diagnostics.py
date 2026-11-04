"""Diagnostic failure must never gate the receiver or hide original failures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from DeviceServers.control.elyse_acq.receiver_process_diagnostics import rotate, run_diagnosed


class ReceiverDiagnosticsTests(unittest.TestCase):
    def test_normal_return_and_original_signature_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            self.assertEqual(run_diagnosed(lambda classes: calls.append(classes) or 17,
                                          ('fixture',), folder), 17)
            self.assertEqual(calls, [('fixture',)])
            rows = [json.loads(line) for line in (Path(folder)/'receiver_lifecycle.jsonl').read_text().splitlines()]
            self.assertEqual([row['event'] for row in rows], ['start', 'exit'])
            self.assertEqual(rows[-1]['code'], 0)
            self.assertEqual(rows[0]['session'], rows[-1]['session'])

    def test_original_exception_and_code_are_preserved(self):
        for error in [RuntimeError('fixture'), SystemExit(5), SystemExit(0)]:
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as folder:
                def fail(classes):
                    raise error
                with self.assertRaises(type(error)) as result:
                    run_diagnosed(fail, (), folder)
                self.assertIs(result.exception, error)
                rows = [json.loads(line) for line in (Path(folder)/'receiver_lifecycle.jsonl').read_text().splitlines()]
                self.assertEqual(rows[-1]['code'], error.code if isinstance(error, SystemExit) else 1)

    def test_unwritable_diagnostics_do_not_prevent_receiver_running(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'not_a_directory'
            path.write_text('fixture')
            self.assertEqual(run_diagnosed(lambda classes: 'running', (), path), 'running')

    def test_native_handler_failure_does_not_prevent_start(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'DeviceServers.control.elyse_acq.receiver_process_diagnostics.faulthandler.enable',
                side_effect=RuntimeError('fixture')):
            self.assertEqual(run_diagnosed(lambda classes: 'running', (), folder), 'running')

    def test_handler_restore_failure_does_not_hide_original_exception(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                'DeviceServers.control.elyse_acq.receiver_process_diagnostics.faulthandler.is_enabled',
                return_value=True), patch(
                'DeviceServers.control.elyse_acq.receiver_process_diagnostics.faulthandler.enable',
                side_effect=[None, RuntimeError('restore failed')]):
            def fail(classes):
                raise ValueError('original failure')
            with self.assertRaisesRegex(ValueError, 'original failure'):
                run_diagnosed(fail, (), folder)

    def test_rotation_keeps_bounded_previous_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test.log'
            path.write_text('first')
            rotate(path, 2)
            self.assertEqual(path.with_suffix('.log.previous').read_text(), 'first')
            path.write_text('second')
            rotate(path, 2)
            self.assertEqual(path.with_suffix('.log.previous').read_text(), 'second')
