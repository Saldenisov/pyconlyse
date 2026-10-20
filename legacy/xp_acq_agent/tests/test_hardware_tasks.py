import unittest
from unittest.mock import Mock, PropertyMock

from nidaqmx.constants import ReadRelativeTo, TerminalConfiguration

from elyse_agent.errors import HardwareWriteBlocked
from elyse_agent.hardware_tasks import create_legacy_card_tasks


class FakeDaqmx(object):
    def __init__(self):
        self.created = []

    def Task(self, new_task_name):
        task = Mock()
        task.new_task_name = new_task_name
        task.is_task_done.side_effect = AssertionError("Task done is not pulse done")
        task.co_channels.add_co_pulse_chan_ticks.return_value.co_pulse_done = True
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
        for name in ("C1_NI6071E_AI", "C2_NI6071E_AI"):
            self.assertEqual(fake.named(name).in_stream.relative_to,
                             ReadRelativeTo.CURRENT_READ_POSITION)
            self.assertIs(fake.named(name).in_stream.auto_start, True)
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
        fake.named("C10_NI6602_CO_3").is_task_done.assert_not_called()
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

    def test_counter_owner_explicit_methods_validate_physical_number(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(True, True, fake)
        for value in (False, True, -1, 8, 3.0, "3", None):
            for method in (owner.start_counter, owner.stop_counter,
                           owner.read_counter_pulse_done):
                with self.assertRaises(ValueError):
                    method(value)
        for number in range(8):
            self.assertIs(owner.read_counter_pulse_done(number), True)
            owner.start_counter(number)
            owner.stop_counter(number)
            task = fake.named("C10_NI6602_CO_" + str(number))
            task.start.assert_called_once_with()
            task.stop.assert_called_once_with()
            task.is_task_done.assert_not_called()
        owner.close()
        for method in (owner.start_counter, owner.stop_counter,
                       owner.read_counter_pulse_done):
            with self.assertRaises(RuntimeError):
                method(3)

    def test_pulse_done_requires_channel_capability_and_exact_bool(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(True, True, fake)
        for value in (0, 1, None, "False", object()):
            owner.counter_channels[3].co_pulse_done = value
            with self.assertRaises(TypeError):
                owner.read_counter_pulse_done(3)
            with self.assertRaises(TypeError):
                owner.update_counter_microseconds(3, 2000, 50)
        owner.counter_channels[3] = object()
        with self.assertRaises(AttributeError):
            owner.read_counter_pulse_done(3)
        fake.named("C10_NI6602_CO_3").stop.assert_not_called()
        fake.named("C10_NI6602_CO_3").is_task_done.assert_not_called()
        owner.close()

    def test_pulse_done_uses_channel_property_and_manual_22_poll_policy(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(True, True, fake)
        owner.sleep = Mock()
        channel = type("FakePulseChannel", (object,), {})()
        pulse = PropertyMock(return_value=False)
        type(channel).co_pulse_done = pulse
        owner.counter_channels[3] = channel
        owner.update_counter_microseconds(3, 2000, 50)
        self.assertEqual(pulse.call_count, 22)
        self.assertEqual(owner.sleep.call_count, 22)
        owner.close()

    def test_analog_count_and_timeout_rejected_before_read(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(True, True, fake)
        for name in ("C1_NI6071E_AI", "C2_NI6071E_AI", "C11_NI6220_AI"):
            for count in (False, True, 0, -1, 0.5, 1.0, "10", 11, 1000, None):
                with self.assertRaises(ValueError):
                    owner.read_analog_means(name, count)
            for timeout in (False, True, 0, -1, float("inf"), float("nan"),
                            "1", None, 10 ** 1000):
                with self.assertRaises(ValueError):
                    owner.read_analog_means(name, timeout_seconds=timeout)
            fake.named(name).read.assert_not_called()
        owner.close()

    def test_analog_configured_finite_count_is_not_changed_to_1000(self):
        fake = FakeDaqmx()
        owner = create_legacy_card_tasks(True, True, fake)
        task = fake.named("C1_NI6071E_AI")
        task.read.return_value = [[1.0] * 10 for _ in range(64)]
        self.assertEqual(owner.read_analog_means("C1_NI6071E_AI"), [1.0] * 64)
        task.read.assert_called_once_with(number_of_samples_per_channel=10, timeout=10.0)
        self.assertEqual(task.timing.cfg_samp_clk_timing.call_args[1]["samps_per_chan"], 10)
        owner.close()

    def test_ai_read_property_failure_cleans_all_created_tasks(self):
        for field in ("relative_to", "auto_start"):
            fake = FakeDaqmx()
            original = fake.Task
            def factory(new_task_name):
                task = original(new_task_name)
                if new_task_name == "C2_NI6071E_AI":
                    stream = type("FailingStream", (object,), {})()
                    setattr(type(stream), field, PropertyMock(side_effect=RuntimeError("property failure")))
                    task.in_stream = stream
                return task
            fake.Task = factory
            with self.assertRaises(RuntimeError):
                create_legacy_card_tasks(True, True, fake)
            self.assertTrue(fake.created)
            self.assertTrue(all(task.close.called for task in fake.created))

    def test_failed_property_cleanup_retains_unclosed_owner(self):
        from elyse_agent.hardware_tasks import PartialTaskCreationError
        fake = FakeDaqmx()
        original = fake.Task
        def factory(new_task_name):
            task = original(new_task_name)
            if new_task_name == "C1_NI6071E_AI":
                stream = type("FailingStream", (object,), {})()
                type(stream).relative_to = PropertyMock(side_effect=RuntimeError("property failure"))
                task.in_stream = stream
                task.close.side_effect = RuntimeError("close failure")
            return task
        fake.Task = factory
        with self.assertRaises(PartialTaskCreationError) as context:
            create_legacy_card_tasks(True, True, fake)
        owner = context.exception.owner
        self.assertFalse(owner.closed)
        self.assertEqual(list(owner.tasks), ["C1_NI6071E_AI"])
        owner.tasks["C1_NI6071E_AI"].close.side_effect = None
        owner.close()
        self.assertTrue(owner.closed)


if __name__ == "__main__":
    unittest.main()
