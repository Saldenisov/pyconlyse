"""Headless unified startup/shutdown ordering; Python 3.4, RAM collaborators only.

Never creates Tk windows, sockets, SQLite journals, native children, NI tasks,
live process inventories or XP interactions.
"""
import types
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent import acquisition_control_gui as gui
from legacy.xp_acq_control.elyse_agent.application_view import (
    ApplicationShutdown, cleanup_failed_start,
)


class FakeVariable(object):
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value


class FakeWidget(object):
    def __init__(self, master=None, kind=None, **kwargs):
        self.master, self.kind, self.options = master, kind, kwargs
        self.children = []
        if master is not None:
            master.children.append(self)

    def pack(self, **kwargs):
        pass

    def bind(self, *args):
        pass

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def destroy(self):
        pass


class FakeRoot(FakeWidget):
    def __init__(self):
        FakeWidget.__init__(self)
        self.callbacks, self.protocols = [], {}

    def title(self, value):
        self.title_text = value

    def geometry(self, value):
        self.geometry_text = value

    def after(self, delay, callback):
        self.callbacks.append((delay, callback))

    def protocol(self, name, callback):
        self.protocols[name] = callback

    def winfo_children(self):
        return self.children[:]

    def mainloop(self):
        pass


def headless_tk():
    module = types.ModuleType("tkinter")
    module.Tk, module.StringVar = FakeRoot, FakeVariable
    for kind in ("Label", "Button", "Frame", "Text"):
        def construct(master=None, _kind=kind, **kwargs):
            return FakeWidget(master, kind=_kind, **kwargs)
        setattr(module, kind, construct)
    module.messagebox = types.ModuleType("tkinter.messagebox")
    return module


def widgets(root):
    result = []
    for item in root.children:
        result.append(item)
        result.extend(widgets(item))
    return result


class StartupOrderingTests(unittest.TestCase):
    def run_headless_main(self, failure=None):
        events, objects = [], {}
        tk = headless_tk()
        base = dict(read_timeout_seconds=1., period_seconds=.2,
                    bind_host="127.0.0.1", port=8772)
        control = dict(remote_control_enabled=False,
            cooling_safety=dict(polarity_verified=False, journal_file="UNOPENED_FAKE.sqlite3"),
            telemetry=dict(enabled=True, host="10.20.30.202", port=8767, period_seconds=.2))

        class Guard(object):
            def __init__(self, path):
                objects["guard"] = self
                self.path = path

            def acquire(self):
                events.append("guard.acquire")
                if failure == "guard":
                    raise OSError("Synthetic application guard already held")

            def release(self):
                events.append("guard.release")

        class Cooling(object):
            def __init__(self):
                events.append("cooling.ram")
                objects["cooling"] = self

            @classmethod
            def with_journal(cls, *args, **kwargs):
                raise AssertionError("Startup must attach journal to the same guarded RAM policy")

            def attach_owned_journal(self, path, namespace):
                events.append("journal.attach")
                objects["journal_args"] = (path, namespace)
                return self

        class Runtime(object):
            def __init__(self, factory, **kwargs):
                events.append("runtime.construct")
                objects["runtime"] = self
                self.cooling = kwargs["cooling"]

            def start(self):
                events.append("runtime.start")

        class View(object):
            def __init__(self, runtime):
                self.runtime = runtime

            def start(self):
                events.append("view.start")

        class Server(object):
            def __init__(self, *args):
                events.append("http.bind")
                if failure == "http":
                    raise OSError("Synthetic 8772 bind refused")

            def serve_forever(self, **kwargs):
                events.append("http.serve")

        class Publisher(object):
            def __init__(self, *args, **kwargs):
                pass

            def start(self):
                events.append("vi.bind")
                if failure == "vi":
                    raise OSError("Synthetic old bridge owns 8766")

        class InlineThread(object):
            def __init__(self, target):
                self.target = target

            def start(self):
                self.target()

        class Cleanup(object):
            completed, errors = True, []

            def __init__(self, **resources):
                objects["cleanup_resources"] = resources

            def start(self):
                events.append("cleanup.start")

        def window(root, runtime, server, *args, **kwargs):
            events.append("window.open")
            objects["window_guard"] = kwargs["application_guard"]
            objects["root"] = root

        with mock.patch.dict("sys.modules", {"tkinter": tk, "tkinter.messagebox": tk.messagebox}), \
                mock.patch.object(gui, "load_control_configuration", return_value=(base, b"r" * 32, None, control)), \
                mock.patch.object(gui, "FileInstanceGuard", Guard), \
                mock.patch.object(gui, "CoolingSafety", Cooling), \
                mock.patch.object(gui, "AcquisitionControlRuntime", Runtime), \
                mock.patch.object(gui, "ApplicationView", View), \
                mock.patch.object(gui, "ControlHTTPServer", Server), \
                mock.patch.object(gui, "DualModeTelemetryPublisher", Publisher), \
                mock.patch.object(gui, "ControlWindow", side_effect=window), \
                mock.patch.object(gui, "StartupCleanup", Cleanup), \
                mock.patch.object(gui, "LocalHandoverVerifier", return_value=object()), \
                mock.patch.object(gui, "OwnershipMarker", return_value=object()), \
                mock.patch.object(gui, "control_identity", return_value=dict(session_id="a" * 32, build_id="b" * 64)), \
                mock.patch.object(gui, "IsolatedCardBackend", side_effect=AssertionError("Native construction forbidden")), \
                mock.patch.object(gui.threading, "Thread", InlineThread):
            result = gui.main("FAKE_ENTRYPOINT.pyw", ["--config", "FAKE_CONFIG.json"])
        return result, events, objects

    def test_application_guard_refusal_never_opens_journal_or_runtime(self):
        result, events, objects = self.run_headless_main("guard")
        self.assertEqual(result, 1)
        self.assertNotIn("journal.attach", events)
        self.assertNotIn("runtime.construct", events)
        self.assertNotIn("http.bind", events)
        self.assertIs(objects["cleanup_resources"]["application_guard"], objects["guard"])

    def test_http_bind_refusal_never_opens_journal_or_starts_owner(self):
        result, events, objects = self.run_headless_main("http")
        self.assertEqual(result, 1)
        self.assertIn("http.bind", events)
        self.assertNotIn("vi.bind", events)
        self.assertNotIn("journal.attach", events)
        self.assertNotIn("runtime.start", events)

    def test_existing_old_bridge_refuses_before_any_journal_writer(self):
        result, events, objects = self.run_headless_main("vi")
        self.assertEqual(result, 1)
        self.assertIn("vi.bind", events)
        self.assertNotIn("journal.attach", events)
        self.assertNotIn("runtime.start", events)
        self.assertIs(objects["cleanup_resources"]["cooling"], objects["cooling"])

    def test_success_guard_then_http_then_vi_then_journal_then_runtime(self):
        result, events, objects = self.run_headless_main()
        self.assertEqual(result, 0, events)
        ordered = ["guard.acquire", "http.bind", "vi.bind", "journal.attach",
                   "runtime.start", "view.start", "http.serve", "window.open"]
        self.assertEqual([item for item in events if item in ordered], ordered)
        self.assertEqual(events.count("cooling.ram"), 1)
        self.assertIs(objects["runtime"].cooling, objects["cooling"])
        self.assertIs(objects["window_guard"], objects["guard"])
        self.assertEqual(objects["journal_args"], ("UNOPENED_FAKE.sqlite3", "xp_acquisition_control"))

    def test_real_window_constructor_has_exactly_three_lifecycle_buttons(self):
        tk, root = headless_tk(), FakeRoot()
        runtime, server, guard = object(), object(), object()
        with mock.patch.dict("sys.modules", {"tkinter": tk, "tkinter.messagebox": tk.messagebox}):
            window = gui.ControlWindow(root, runtime, server, "FAKE.json", "FAKE.pyw",
                                       application_guard=guard)
        self.assertEqual([item.options["text"] for item in widgets(root) if item.kind == "Button"],
                         ["Initialize", "Deinitialize", "Stop server"])
        self.assertIs(window.shutdown.application_guard, guard)


class CleanupResources(object):
    def __init__(self, failure=None):
        self.events, self.failure, self.guard_released = [], failure, False
        owner = self

        def step(name):
            owner.events.append(name)
            if owner.failure == name:
                raise RuntimeError("Synthetic " + name + " failure")

        class Runtime(object):
            def join(self, timeout):
                step("ni.join")
                return owner.failure != "ni.join.false"

            def request_shutdown(self):
                step("ni.request_shutdown")

        class Publisher(object):
            def close(self):
                step("publisher.close")

        class Server(object):
            def shutdown(self):
                step("http.shutdown")

            def server_close(self):
                step("http.close")

        class View(object):
            def close(self, timeout=1):
                step("view.close")

        class Cooling(object):
            def snapshot(self):
                step("journal.snapshot")

            def close(self, timeout=1):
                step("journal.close")
                return owner.failure != "journal.close.false"

        class Guard(object):
            def release(self):
                step("guard.release")
                owner.guard_released = True

        class Thread(object):
            def is_alive(self):
                return True

        self.runtime, self.publisher, self.server = Runtime(), Publisher(), Server()
        self.view, self.cooling, self.guard, self.server_thread = View(), Cooling(), Guard(), Thread()
        self.runtime.telemetry_publisher, self.runtime.cooling = self.publisher, self.cooling


class ShutdownGuardTests(unittest.TestCase):
    def shutdown(self, resources):
        closer = ApplicationShutdown(resources.runtime, resources.server, resources.view,
                                     application_guard=resources.guard)
        closer.start()
        closer.worker.join(2)
        self.assertFalse(closer.worker.is_alive(), "RAM-only shutdown did not finish")
        return closer

    def failed_start(self, resources):
        return cleanup_failed_start(runtime=resources.runtime, server=resources.server,
            view=resources.view, publisher=resources.publisher, cooling=resources.cooling,
            server_thread=resources.server_thread, application_guard=resources.guard, timeout=.01)

    def test_normal_shutdown_releases_guard_only_after_all_owners_and_workers(self):
        resources = CleanupResources()
        closer = self.shutdown(resources)
        self.assertTrue(closer.completed, closer.error)
        self.assertTrue(resources.guard_released)
        self.assertEqual(resources.events, ["ni.join", "publisher.close", "http.shutdown",
                         "http.close", "journal.close", "view.close", "guard.release"])

    def test_shutdown_keeps_guard_on_each_join_or_close_failure(self):
        for failure in ("ni.join.false", "ni.join", "publisher.close", "http.shutdown",
                        "http.close", "journal.close.false", "journal.close", "view.close"):
            resources = CleanupResources(failure)
            closer = self.shutdown(resources)
            self.assertFalse(closer.completed, failure)
            self.assertTrue(closer.error, failure)
            self.assertFalse(resources.guard_released, failure)
            self.assertNotIn("guard.release", resources.events, failure)

    def test_failed_start_cleanup_releases_guard_last_after_clean_joins(self):
        resources = CleanupResources()
        self.assertEqual(self.failed_start(resources), [])
        self.assertTrue(resources.guard_released)
        self.assertEqual(resources.events, ["ni.request_shutdown", "ni.join", "publisher.close",
                         "http.shutdown", "http.close", "view.close", "journal.snapshot",
                         "journal.close", "guard.release"])

    def test_failed_start_cleanup_retains_guard_on_any_resource_error(self):
        for failure in ("ni.request_shutdown", "ni.join.false", "ni.join", "publisher.close",
                        "http.shutdown", "http.close", "view.close", "journal.snapshot",
                        "journal.close.false", "journal.close"):
            resources = CleanupResources(failure)
            self.assertTrue(self.failed_start(resources), failure)
            self.assertFalse(resources.guard_released, failure)
            self.assertNotIn("guard.release", resources.events, failure)

    def test_failed_owner_join_retains_network_journal_and_guard(self):
        resources = CleanupResources("ni.join.false")
        self.assertTrue(self.failed_start(resources))
        self.assertEqual(resources.events, ["ni.request_shutdown", "ni.join"])
        self.assertFalse(resources.guard_released)


if __name__ == "__main__":
    unittest.main()
