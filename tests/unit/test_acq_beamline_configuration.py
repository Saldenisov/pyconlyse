"""Cold configuration boundaries, actual Python 3.4, no Tk/NI or equipment."""
import json
import os
import tempfile
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_gui import load_configuration
from legacy.xp_acq_control.elyse_agent.acquisition_control_gui import BUTTON_LABELS
from legacy.xp_acq_control.elyse_agent.runtime_identity import SOURCE_PATHS


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


class BeamlineConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = os.path.join(self.folder.name, 'config.json')
        with open(os.path.join(ROOT, 'legacy', 'xp_acq_control', 'config.acquisition.json')) as source:
            self.config = json.load(source)
        self.config['key_file'] = 'fixture.key'
        with open(os.path.join(self.folder.name, 'fixture.key'), 'wb') as target:
            target.write(b'test-only-cold-configuration-key-000000000')

    def load(self):
        with open(self.path, 'w') as target:
            json.dump(self.config, target)
        return load_configuration(self.path)[0]

    def test_packaged_beamline_and_existing_commissioning_remain_false(self):
        self.assertIs(self.config['beamline_controls_verified'], False)
        for key, value in self.config.items():
            if key.endswith('_verified'):
                self.assertIs(value, False, key)
        self.assertEqual(BUTTON_LABELS, ('Initialize', 'Deinitialize', 'Stop server'))
        with open(os.path.join(ROOT, 'legacy', 'xp_acq_control', 'config.acquisition.control.json')) as source:
            self.assertIs(json.load(source)['remote_control_enabled'], False)

    def test_explicit_boolean_only_and_legacy_absence_defaults_false(self):
        for value in (False, True):
            self.config['beamline_controls_verified'] = value
            self.assertIs(self.load()['beamline_controls_verified'], value)
        self.config.pop('beamline_controls_verified')
        self.assertIs(self.load().get('beamline_controls_verified', False), False)

    def test_coercible_or_unknown_motion_flags_are_rejected(self):
        for value in (0, 1, 'true', None, [], {}):
            self.config['beamline_controls_verified'] = value
            self.assertRaises(ValueError, self.load)
        self.config['beamline_controls_verified'] = False
        self.config['allow_faraday_hors'] = True
        self.assertRaises(ValueError, self.load)

    def test_cold_backend_does_not_allocate_or_qualify_position_feedback(self):
        from legacy.xp_acq_control.elyse_agent.acquisition_backend import CardBackend
        calls = []
        backend = CardBackend(factory=lambda **kwargs: calls.append(kwargs),
                              beamline_controls_verified=True)
        self.assertEqual(calls, [])
        self.assertEqual(backend.resource_count, 0)
        self.assertIs(backend.beamline_controls_verified, True)
        self.assertIs(backend.stage_controls_verified, False)
        self.assertIs(backend.ht_feedback_verified, False)

    def test_motion_source_is_inside_explicit_fingerprint_closure(self):
        self.assertEqual(SOURCE_PATHS.count('elyse_agent/acquisition_beamline.py'), 1)
        self.assertFalse(any('runtime/' in path for path in SOURCE_PATHS))


if __name__ == '__main__':
    unittest.main()
