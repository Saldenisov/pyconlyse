"""RAM driver boundaries only; no NI/XP/network. Actual Python 3.4 compatible."""
import base64
import ctypes
import json
import unittest

from legacy.xp_acq_control.elyse_agent.supervision_cards import (
    SupervisionCounterCard, SupervisionCardError,
)
from legacy.xp_acq_control.elyse_agent.supervision_imaq import (
    SupervisionVideoCard, source_video_configuration, CtypesIMAQ,
    ATTR_WHITE_REF_VOLT, ATTR_BLACK_REF_VOLT, ATTR_CHANNEL, ATTR_FRAMEWAIT_MSEC,
    ATTR_ROI_WIDTH, ATTR_ROI_HEIGHT, ATTR_ROWPIXELS, ATTR_BYTESPERPIXEL, ATTR_IMAGE_TYPE,
)
from legacy.xp_acq_control.elyse_agent.synchronization_profiles import (
    supervision_counter_profile, source_timing_pairs,
)
from legacy.xp_acq_control.elyse_agent.isolated_wire import encode_frame


class Object(object):
    pass


class FakeChannel(object):
    def __init__(self, trace, number, failure):
        object.__setattr__(self, "trace", trace)
        object.__setattr__(self, "number", number)
        object.__setattr__(self, "failure", failure)
        object.__setattr__(self, "done", True)

    def __setattr__(self, name, value):
        if name.startswith("co_"):
            self.trace.append(("property", self.number, name, value))
            if self.failure == name:
                raise IOError("injected property failure")
        object.__setattr__(self, name, value)

    @property
    def co_pulse_done(self):
        self.trace.append(("done", self.number))
        return self.done


class FakeTask(object):
    def __init__(self, trace, number, failure):
        self.trace, self.number = trace, number
        self.channel = FakeChannel(trace, number, failure)
        self.co_channels = Object()
        self.co_channels.add_co_pulse_chan_ticks = self.add_channel
        self.triggers, self.timing = Object(), Object()
        self.triggers.start_trigger = Object()
        self.triggers.start_trigger.cfg_dig_edge_start_trig = self.trigger
        self.timing.cfg_implicit_timing = self.timing_call

    def add_channel(self, physical, timebase, **values):
        self.trace.append(("channel", self.number, physical, timebase, values))
        return self.channel

    def trigger(self, source, **values):
        self.trace.append(("trigger", self.number, source, values))

    def timing_call(self, **values):
        self.trace.append(("timing", self.number, values))

    def start(self):
        self.trace.append(("start", self.number))

    def stop(self):
        self.trace.append(("stop", self.number))

    def close(self):
        self.trace.append(("close", self.number))


class FakeDriver(object):
    def __init__(self, fail_create=None, fail_property=None):
        self.trace, self.tasks = [], {}
        self.fail_create, self.fail_property = fail_create, fail_property
        self.constants = Object()
        for name, field, value in (("Level", "LOW", "LOW"), ("Edge", "RISING", "RISING"),
                                   ("AcquisitionType", "FINITE", "FINITE")):
            item = Object()
            setattr(item, field, value)
            setattr(self.constants, name, item)

    def Task(self, new_task_name):
        number = int(new_task_name[len("SUPCOUNT"):])
        self.trace.append(("create", number, new_task_name))
        if number == self.fail_create:
            raise IOError("injected native constructor failure")
        task = FakeTask(self.trace, number, self.fail_property)
        self.tasks[number] = task
        return task


class FakeVideo(object):
    def __init__(self):
        self.trace = []
        self.fail = None
        self.frame = dict(width=3, height=2, data=bytes(range(6)), pixel_type="U8")

    def open_interface(self, name):
        self.trace.append(("interface", name))
        return 101

    def open_session(self, interface):
        self.trace.append(("session", interface))
        if self.fail == "session":
            raise IOError("injected session open failure")
        return 102

    def set_attribute(self, session, attribute, value):
        self.trace.append(("attribute", session, attribute, value))

    def grab_setup(self, session):
        self.trace.append(("setup", session))

    def grab(self, session, maximum):
        self.trace.append(("grab", session, maximum))
        if self.fail == "grab":
            raise IOError("injected grab failure")
        return self.frame

    def stop(self, session):
        self.trace.append(("stop", session))

    def close(self, session):
        self.trace.append(("close", session))
        if self.fail == "close" and session == 102:
            raise IOError("injected session close failure")


class SupervisionCardAdapterTests(unittest.TestCase):
    def test_counter_profile_matches_all_sixteen_live_ui_values(self):
        values = source_timing_pairs(supervision_counter_profile())
        self.assertEqual(values, (.35, .35, 2176., 100., 2008.3, 10., 2175., 10.,
                                 2175., 100., 500., 500., .3, 10., 2175., 100.))
        self.assertTrue(all(row["initial_delay_ticks"] == 0 for row in supervision_counter_profile()))
        self.assertTrue(all(row["physical_timebase_hz"] is None for row in supervision_counter_profile()))

    def test_cold_construction_and_confirmation_have_no_driver_effect(self):
        driver = FakeDriver()
        calls = []
        owner = SupervisionCounterCard(driver_factory=lambda: calls.append("load") or driver)
        self.assertEqual(calls, [])
        for confirmed, released in ((False, True), (True, False), (1, True)):
            self.assertRaises(ValueError, owner.initialize, confirmed, released)
        self.assertEqual(calls, [])
        self.assertEqual(driver.trace, [])
        self.assertEqual(owner.resource_count, 0)

    def test_source_configure_and_start_per_frame_all_eight(self):
        driver = FakeDriver()
        owner = SupervisionCounterCard(driver_factory=lambda: driver)
        result = owner.initialize(True, True)
        self.assertEqual(result["resource_count"], 8)
        self.assertEqual(result["synchronization"]["running_counters"], list(range(8)))
        for i, row in enumerate(supervision_counter_profile()):
            channel = next(x for x in driver.trace if x[:2] == ("channel", i))
            self.assertEqual(channel[2:4], (row["physical_channel"], "/Dev1/PFI11"))
            self.assertEqual(channel[4], dict(idle_state="LOW", initial_delay=0,
                                              low_ticks=row["low_ticks"], high_ticks=row["high_ticks"]))
            self.assertIn(("trigger", i, "/Dev1/PFI10", {"trigger_edge": "RISING"}), driver.trace)
            self.assertIn(("timing", i, {"sample_mode": "FINITE", "samps_per_chan": 1}), driver.trace)
            if i < 7:
                self.assertLess(driver.trace.index(("start", i)),
                                driver.trace.index(("create", i + 1, "SUPCOUNT" + str(i + 1))))
        owner.close()
        self.assertEqual(owner.resource_count, 0)

    def test_constructor_failure_never_certifies_lost_handle_release(self):
        driver = FakeDriver(fail_create=2)
        owner = SupervisionCounterCard(driver_factory=lambda: driver)
        with self.assertRaises(SupervisionCardError) as error:
            owner.initialize(True, True)
        self.assertIs(error.exception.owner, owner)
        self.assertTrue(owner.creation_uncertain)
        self.assertEqual(sorted(owner.tasks), [0, 1])
        self.assertRaises(SupervisionCardError, owner.close)
        self.assertEqual(owner.resource_count, 1)

    def test_runtime_timing_stop_then_three_properties_then_start(self):
        driver = FakeDriver()
        owner = SupervisionCounterCard(driver_factory=lambda: driver)
        owner.initialize(True, True)
        driver.trace[:] = []
        result = owner.configure_timing(2, 2008.3, 10., True)
        self.assertEqual(driver.trace, [("done", 2), ("stop", 2),
            ("property", 2, "co_pulse_ticks_initial_delay", 40166),
            ("property", 2, "co_pulse_low_ticks", 40166),
            ("property", 2, "co_pulse_high_ticks", 200), ("start", 2)])
        self.assertEqual(result["initial_delay_ticks"], 40166)
        owner.close()

    def test_partial_property_failure_never_restarts_or_replays(self):
        driver = FakeDriver()
        owner = SupervisionCounterCard(driver_factory=lambda: driver)
        owner.initialize(True, True)
        driver.tasks[2].channel.failure = "co_pulse_low_ticks"
        driver.trace[:] = []
        self.assertRaises(SupervisionCardError, owner.configure_timing, 2, 1., 2., True)
        self.assertNotIn(("start", 2), driver.trace)
        self.assertIn(2, owner.uncertain)
        prior = list(driver.trace)
        self.assertRaises(ValueError, owner.configure_timing, 2, 1., 2., True)
        self.assertEqual(driver.trace, prior)
        owner.close()

    def test_bounded_supervision_wait_adds_no_source_iteration_limit(self):
        driver = FakeDriver()
        clock = [0.]
        owner = SupervisionCounterCard(driver_factory=lambda: driver,
            wait=lambda seconds: clock.__setitem__(0, clock[0] + seconds), clock=lambda: clock[0])
        owner.initialize(True, True)
        driver.tasks[1].channel.done = False
        driver.trace[:] = []
        self.assertRaises(TimeoutError, owner.configure_timing, 1, 1., 2., True, .01)
        self.assertFalse(any(x[0] in ("stop", "start", "property") for x in driver.trace))
        owner.close()

    def test_video_explicit_source_defaults_and_init_order(self):
        driver = FakeVideo()
        owner = SupervisionVideoCard(driver=driver)
        self.assertRaises(ValueError, owner.initialize, source_video_configuration())
        self.assertEqual(driver.trace, [])
        owner.initialize(source_video_configuration(), True, True)
        self.assertEqual(driver.trace, [("interface", "img0"), ("session", 101),
            ("attribute", 102, ATTR_WHITE_REF_VOLT, .9),
            ("attribute", 102, ATTR_BLACK_REF_VOLT, .1),
            ("attribute", 102, ATTR_CHANNEL, 2),
            ("attribute", 102, ATTR_FRAMEWAIT_MSEC, 500), ("setup", 102)])
        self.assertFalse(owner.snapshot()["C12NI1409_contains_pixels"])
        owner.close()
        self.assertEqual(driver.trace[-3:], [("stop", 102), ("close", 102), ("close", 101)])

    def test_video_frame_is_raw_bounded_and_private_ipc_serializable(self):
        driver = FakeVideo()
        owner = SupervisionVideoCard(driver=driver)
        owner.initialize(source_video_configuration(), True, True)
        frame = owner.read_frame()
        self.assertEqual(base64.b64decode(frame["data"]), bytes(range(6)))
        self.assertEqual((frame["width"], frame["height"], frame["sequence"]), (3, 2, 1))
        self.assertTrue(encode_frame(dict(frame=frame)))
        driver.frame["data"] = b"invalid length"
        self.assertRaises(ValueError, owner.read_frame)
        self.assertEqual(owner.sequence, 1)
        driver.fail = "grab"
        self.assertRaises(IOError, owner.read_frame)
        self.assertEqual(owner.sequence, 1)
        owner.close()

    def test_camera_unknown_open_and_failed_close_retain_resources(self):
        driver = FakeVideo()
        driver.fail = "session"
        owner = SupervisionVideoCard(driver=driver)
        self.assertRaises(SupervisionCardError, owner.initialize, source_video_configuration(), True, True)
        self.assertTrue(owner.creation_uncertain)
        self.assertRaises(SupervisionCardError, owner.close)
        self.assertEqual(owner.resource_count, 1)
        driver = FakeVideo()
        owner = SupervisionVideoCard(driver=driver)
        owner.initialize(source_video_configuration(), True, True)
        driver.fail = "close"
        self.assertRaises(SupervisionCardError, owner.close)
        self.assertEqual(owner.session, 102)
        self.assertEqual(owner.resource_count, 2)
        driver.fail = None
        owner.close()
        self.assertEqual(owner.resource_count, 0)

    def test_native_buffer_rows_are_copied_without_padding(self):
        class NativeFixture(CtypesIMAQ):
            def __init__(self):
                CtypesIMAQ.__init__(self)
                self.ctypes = ctypes
                self.pixels = b"abcXdefY"
                self.addresses = []
                self.trace = []
                self.fail_close = False

            def get_u32(self, session, attribute):
                return {ATTR_ROI_WIDTH: 3, ATTR_ROI_HEIGHT: 2, ATTR_ROWPIXELS: 4,
                        ATTR_BYTESPERPIXEL: 1, ATTR_IMAGE_TYPE: 0}[attribute]

            def _call(self, name, *args):
                self.trace.append(name)
                if name == "imgSessionGetBufferSize":
                    args[1]._obj.value = len(self.pixels)
                elif name == "imgGrab":
                    address = args[1]._obj.value
                    if not address:
                        raise AssertionError("Repeated NULL output-buffer allocation")
                    self.addresses.append(address)
                    ctypes.memmove(address, self.pixels, len(self.pixels))
                elif name == "imgClose" and self.fail_close:
                    raise IOError("injected native close failure")
        driver = NativeFixture()
        first = driver.grab(102, 8)
        self.assertEqual(first, dict(width=3, height=2, data=b"abcdef", pixel_type="U8"))
        self.assertEqual(driver.trace, ["imgSessionGetBufferSize", "imgGrab"])
        driver.pixels = b"ghiXjklY"
        second = driver.grab(102, 8)
        self.assertEqual(first['data'], b"abcdef")  # Owned bytes survive the next grab.
        self.assertEqual(second['data'], b"ghijkl")
        self.assertEqual(driver.addresses[0], driver.addresses[1])
        self.assertEqual(ctypes.sizeof(driver._grab_buffers[102]), 8)
        driver.pixels += b"pad!"
        self.assertEqual(driver.grab(102, 8)['data'], b"ghijkl")
        self.assertEqual(ctypes.sizeof(driver._grab_buffers[102]), 12)
        driver.trace[:] = []
        self.assertRaises(ValueError, driver.grab, 102, 5)
        self.assertEqual(driver.trace, ["imgSessionGetBufferSize"])
        driver.fail_close = True
        self.assertRaises(IOError, driver.close, 102)
        self.assertIn(102, driver._grab_buffers)
        driver.fail_close = False
        driver.close(102)
        self.assertEqual(driver._grab_buffers, {})

    def test_video_largest_supported_frame_fits_existing_ipc_limit(self):
        driver = FakeVideo()
        driver.frame = dict(width=1024, height=512, data=b"\x00" * 524288, pixel_type="U8")
        owner = SupervisionVideoCard(driver=driver)
        owner.initialize(source_video_configuration(), True, True)
        self.assertLess(len(encode_frame(dict(frame=owner.read_frame()))), 1048576)
        owner.close()


if __name__ == "__main__":
    unittest.main()
