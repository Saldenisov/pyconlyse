import unittest

from elyse_agent.input_probe import discover_inventory, probe_card


class FakeTask(object):
    def __init__(self, owner):
        self.owner = owner
        self.ai_channels = self
        self.closed = False

    def add_ai_voltage_chan(self, physical, terminal_config, min_val, max_val):
        self.owner.configured.append((physical, terminal_config, min_val, max_val))

    def read(self, timeout):
        if self.owner.fail_read:
            raise RuntimeError("driver read failed")
        return 1.25

    def close(self):
        self.closed = True


class FakeDaqmx(object):
    class constants(object):
        class TerminalConfiguration(object):
            DIFFERENTIAL = "DIFFERENTIAL"
            RSE = "RSE"

    def __init__(self, fail_read=False):
        self.fail_read = fail_read
        self.configured = []
        self.tasks = []

    def Task(self):
        task = FakeTask(self)
        self.tasks.append(task)
        return task


class FakeChannelCollection(object):
    def __init__(self, names):
        self.channel_names = names


class FakeAuditDevice(object):
    def __init__(self, name, product_type):
        self.name = name
        self.product_type = product_type
        self.dev_serial_num = 1234
        self.dev_is_simulated = False
        for attribute in (
            "ai_physical_chans", "ao_physical_chans", "di_lines",
            "do_lines", "ci_physical_chans", "co_physical_chans"
        ):
            setattr(self, attribute, FakeChannelCollection([]))
        self.ao_physical_chans = FakeChannelCollection([name + "/ao0"])


class FakeAuditDaqmx(object):
    class system(object):
        class System(object):
            @staticmethod
            def local():
                class Version(object):
                    major_version = 9
                    minor_version = 6
                    update_version = 2

                class LocalSystem(object):
                    driver_version = Version()
                    devices = [
                        FakeAuditDevice("6", "PCI-6703"),
                        FakeAuditDevice("10", "PCI-6602"),
                    ]

                return LocalSystem()

    def Task(self):
        raise AssertionError("inventory must not create tasks")


class InputProbeTests(unittest.TestCase):
    def test_capability_inventory_queries_cards_without_tasks(self):
        report = discover_inventory(daqmx=FakeAuditDaqmx())
        self.assertEqual(report["device_count"], 2)
        self.assertEqual(report["driver_version"], "9.6.2")
        self.assertEqual(report["devices"][0]["channel_counts"]["ao"], 1)
        self.assertEqual(report["devices"][0]["status"], "queried")
        self.assertEqual(report["tasks_created"], 0)
        self.assertEqual(report["readings_taken"], 0)
        self.assertFalse(report["hardware_writes"])

    def test_digital_and_output_cards_are_rejected_before_task_creation(self):
        fake = FakeDaqmx()
        for card in ("C3_DIO96_DI", "C3_DIO96_DO", "C6_NI6703_AO", "C10_NI6602_CO"):
            with self.assertRaises(ValueError):
                probe_card(card, daqmx=fake)
        self.assertEqual(fake.tasks, [])

    def test_first_analog_input_is_read_and_task_is_closed(self):
        fake = FakeDaqmx()
        result = probe_card("C1_NI6071E_AI", daqmx=fake)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["results"][0]["physical_channel"], "/1/ai0")
        self.assertEqual(result["results"][0]["value"], 1.25)
        self.assertEqual(fake.configured[0], ("/1/ai0", "DIFFERENTIAL", -10.0, 10.0))
        self.assertTrue(fake.tasks[0].closed)
        self.assertFalse(result["hardware_writes"])

    def test_driver_error_stops_card_and_closes_task(self):
        fake = FakeDaqmx(fail_read=True)
        result = probe_card("C11_NI6220_AI", scope="all", daqmx=fake)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["attempted"], 1)
        self.assertEqual(result["error"]["message"], "driver read failed")
        self.assertEqual(fake.configured[0][2:], (-0.2, 0.2))
        self.assertTrue(fake.tasks[0].closed)

    def test_second_half_rse_is_limited_to_analog_channels(self):
        fake = FakeDaqmx()
        result = probe_card("C11_NI6220_AI", scope="ai8_plus_rse", daqmx=fake)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["read_count"], 8)
        self.assertEqual(fake.configured[0], ("/11/ai8", "RSE", -0.2, 0.2))
        self.assertEqual(fake.configured[-1][0], "/11/ai15")
        self.assertTrue(all(task.closed for task in fake.tasks))
        self.assertFalse(result["hardware_writes"])

    def test_whole_card_uses_driver_supported_terminal_modes(self):
        fake = FakeDaqmx()
        result = probe_card("C11_NI6220_AI", scope="all", daqmx=fake)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["read_count"], 16)
        self.assertEqual(fake.configured[7][1], "DIFFERENTIAL")
        self.assertEqual(fake.configured[8][1], "RSE")
        self.assertFalse(result["hardware_writes"])


if __name__ == "__main__":
    unittest.main()
