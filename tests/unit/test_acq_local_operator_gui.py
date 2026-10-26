"""Headless local GUI callbacks; actual Python3.4, no Tk or NI execution."""
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent.acquisition_control_gui import (
    ControlWindow, initialize_available, application_alarm_text, BUTTON_LABELS)
from legacy.xp_acq_control.elyse_agent.handover_recovery import HANDOVER_CONFIRMATION


def state():
    return dict(state='RECOVERY_REQUIRED', resource_count=0,
        local_handover_available=True, application_view_current=True,
        local_request_pending=None, telemetry_delivery=dict(vi_initialize_exclusion_active=False),
        cooling_safety=dict(active=False, circuits=[], journal_error='old gap',
            journal_storage_error='', journal_history_warning='old gap',
            journal_history_acknowledge_available=True, journal_revision=7))


class LocalOperatorGUITests(unittest.TestCase):
    def window(self, value=None):
        window = ControlWindow.__new__(ControlWindow)
        window.runtime = mock.Mock()
        window.runtime.snapshot.return_value = state() if value is None else value
        window.root, window.messagebox = object(), mock.Mock()
        window.closing, window.demo = False, False
        window.messagebox.askyesno.return_value = True
        return window

    def test_three_buttons_and_current_vi_fence(self):
        self.assertEqual(BUTTON_LABELS, ('Initialize', 'Deinitialize', 'Stop server'))
        value = state()
        self.assertTrue(initialize_available(value))
        value['telemetry_delivery']['vi_initialize_exclusion_active'] = True
        self.assertFalse(initialize_available(value))
        window = self.window(value)
        window.initialize()
        self.assertFalse(window.runtime.initialize_after_handover.called)
        self.assertFalse(window.messagebox.askyesno.called)

    def test_explicit_handover_confirmation_dispatches_only_local_named_request(self):
        window = self.window()
        with mock.patch('getpass.getuser', return_value='local operator'):
            window.initialize()
        window.runtime.initialize_after_handover.assert_called_once_with(
            startup_confirmed=True, electrical_off_confirmed=True,
            confirmation=HANDOVER_CONFIRMATION, operator='local operator')
        self.assertFalse(window.runtime.initialize.called)

    def test_declined_handover_never_clears_or_initializes(self):
        window = self.window()
        window.messagebox.askyesno.return_value = False
        window.initialize()
        self.assertFalse(window.runtime.initialize_after_handover.called)
        self.assertFalse(window.runtime.recover_local.called)

    def test_journal_acknowledgment_is_revision_bound_and_has_no_ni_lifecycle_request(self):
        window = self.window()
        with mock.patch('getpass.getuser', return_value='local operator'):
            window.acknowledge_journal_history()
        request = window.runtime.acknowledge_journal_history.call_args[1]
        self.assertEqual(request['operator'], 'local operator')
        self.assertEqual(request['expected_revision'], 7)
        self.assertIn('not reconstructed', request['reason'])
        self.assertFalse(window.runtime.initialize.called)
        self.assertFalse(window.runtime.initialize_after_handover.called)
        self.assertTrue(window._journal_prompted)

    def test_unhealthy_writer_cannot_be_acknowledged_away(self):
        value = state()
        value['cooling_safety']['journal_history_acknowledge_available'] = False
        window = self.window(value)
        window.acknowledge_journal_history()
        self.assertFalse(window.messagebox.askyesno.called)
        self.assertFalse(window.runtime.acknowledge_journal_history.called)

    def test_history_ack_never_hides_current_storage_error_or_circulation_countdown(self):
        value = state()
        value['cooling_safety'].update(active=True, circuits=[dict(circuit='SECTION')],
            remaining_seconds=42, stop_state='NONE', automatic_stop_available=True,
            journal_history_warning='', journal_error='disk failed', journal_storage_error='disk failed')
        rendered = application_alarm_text(value)
        self.assertIn('SECTION', rendered)
        self.assertIn('42', rendered)
        self.assertIn('disk failed', rendered)
        self.assertNotIn('old gap', rendered)

    def test_confirmed_red_indication_does_not_crash_refresh_or_claim_a_countdown(self):
        value = state()
        value['cooling_safety'].update(active=True, circuits=[dict(circuit='SECTION')],
            countdown_required=False, remaining_seconds=None, stop_state='NONE',
            automatic_stop_available=True, journal_history_warning='', journal_error='')
        rendered = application_alarm_text(value)
        self.assertIn('COOLING INDICATION RED: SECTION', rendered)
        self.assertIn('confirmed by operator', rendered)
        self.assertNotIn('countdown:', rendered)


if __name__ == '__main__':
    unittest.main()
