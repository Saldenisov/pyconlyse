import unittest

from elyse_agent.input_tasks import InputTaskCreationBlocked, create_legacy_input_tasks


class InputTaskTests(unittest.TestCase):
    def test_creation_is_blocked_by_default_before_importing_nidaqmx(self):
        with self.assertRaises(InputTaskCreationBlocked):
            create_legacy_input_tasks()


if __name__ == "__main__":
    unittest.main()
