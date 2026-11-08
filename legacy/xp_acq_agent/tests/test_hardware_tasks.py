import unittest
from unittest.mock import Mock

from nidaqmx.constants import TerminalConfiguration

from elyse_agent.errors import HardwareWriteBlocked
from elyse_agent.hardware_tasks import create_legacy_card_tasks


class FakeDaqmx(object):
    def __init__(self):
        self.created = []

    def Task(self, new_task_name):
        task = Mock()
        task.new_task_name = new_task_name
        task.is_task_done.return_value = True
        self.created.append(task)
        return task

    def named(self, name):
        for task in self.created:
            if task.new_task_name == name:
                return task
        raise KeyError(name)


class HardwareTaskTests(unittest.TestCase):
    def test_default_gate_rejects_even_task_creation(self):
        fake = FakeDaqmx()
        with self.assertRaises(HardwareWriteBlocked):
            create_legacy_card_tasks(daqmx=fake)
        with self.assertRaises(HardwareWriteBlocked):
            create_legacy_card_tasks(authorized=True, daqmx=fake)
        self.assertEqual(fake.created, [])

    def test_manual_configuration_covers_cards_without_start_or_write(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(
            authorized=True, outputs_commissioned=True, daqmx=fake
        )
        self.assertEqual(len(fake.created), 21)
        for task in fake.created:
            task.start.assert_not_called()
            task.write.assert_not_called()
        counter = fake.named("C10_NI6602_CO_2")
        kwargs = counter.co_channels.add_co_pulse_chan_ticks.call_args[1]
        self.assertEqual(kwargs["low_ticks"], 43558)
        self.assertEqual(kwargs["high_ticks"], 200)
        self.assertEqual(kwargs["initial_delay"], 0)
        card1 = fake.named("C1_NI6071E_AI")
        self.assertEqual(
            card1.ai_channels.add_ai_voltage_chan.call_args[1]["terminal_config"],
            TerminalConfiguration.RSE,
        )
        card11 = fake.named("C11_NI6220_AI")
        self.assertEqual(
            card11.ai_channels.add_ai_voltage_chan.call_args[1]["terminal_config"],
            TerminalConfiguration.RSE,
        )
        owner.close()
        self.assertTrue(all(task.close.called for task in fake.created))

    def test_startup_writes_are_a_separate_explicit_step(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(
            authorized=True, outputs_commissioned=True, daqmx=fake
        )
        image = owner.write_initial_images()
        self.assertTrue(fake.named("C3_DIO96_DO").write.called)
        self.assertTrue(fake.named("C8NI6703_AO").write.called)
        self.assertEqual(
            [i for i, value in enumerate(image["digital"]["C3_DIO96_DO"]) if value],
            [1, 4],
        )
        self.assertEqual(
            [i for i, value in enumerate(image["digital"]["C5_DIO96_DO"]) if value],
            [33],
        )
        self.assertAlmostEqual(image["analog_volts"]["C8NI6703"][6], 9.0)
        self.assertEqual(owner.start_legacy_counters(), [0, 1, 2, 5, 6, 7])
        self.assertFalse(fake.named("C10_NI6602_CO_3").start.called)
        owner.close()

    def test_counter_update_uses_delay_for_initial_and_low_ticks(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(
            authorized=True, outputs_commissioned=True, daqmx=fake
        )
        result = owner.update_counter_microseconds(3, 2000, 50)
        self.assertEqual(result["initial_delay_ticks"], 40000)
        self.assertEqual(result["low_ticks"], 40000)
        self.assertEqual(result["high_ticks"], 1000)
        channel = owner.counter_channels[3]
        self.assertEqual(channel.co_pulse_ticks_initial_delay, 40000)
        self.assertEqual(channel.co_pulse_low_ticks, 40000)
        self.assertEqual(channel.co_pulse_high_ticks, 1000)
        owner.close()

    def test_fractional_counter_number_is_rejected_before_output_change(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(
            authorized=True, outputs_commissioned=True, daqmx=fake
        )
        with self.assertRaises(ValueError):
            owner.update_counter_microseconds(3.5, 2000, 50)
        fake.named("C10_NI6602_CO_3").stop.assert_not_called()
        owner.close()


if __name__ == "__main__":
    unittest.main()
