"""Isolated registration tests; no live Tango database or hardware."""

import tempfile
import unittest
from pathlib import Path

from DeviceServers.control.elyse_acq.add_ds_AcqTelemetry import (
    DEVICE,
    SERVER,
    deployment_plan,
    register,
)


class FakeDatabase:
    def __init__(self, devices=(), servers=()):
        self.devices, self.servers, self.writes = devices, servers, []

    def get_device_name(self, *_):
        return self.devices

    def get_server_list(self):
        return self.servers

    def add_device(self, device):
        self.writes.append(("device", device.name, device._class, device.server))

    def put_device_property(self, name, properties):
        self.writes.append(("properties", name, properties))

    def put_server_info(self, server):
        self.writes.append(
            ("server", server.name, server.host, server.mode, server.level)
        )


class RegistrationTests(unittest.TestCase):
    def plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            key = Path(temporary) / "fixture.key"
            key.write_bytes(b"fixture-key-not-a-production-secret-0123456789")
            return deployment_plan(key)

    def test_continuous_fixture_only_plan_has_no_deadline_or_hardware_properties(self):
        plan = self.plan()
        self.assertIsNone(plan["stop_deadline"])
        self.assertEqual(plan["properties"]["producer_kind_filter"], "fixture")
        self.assertEqual(plan["properties"]["listen_port"], 8767)
        self.assertEqual((plan["mode"], plan["level"]), (1, 1))
        self.assertEqual(
            set(plan["properties"]),
            {
                "listen_host",
                "listen_port",
                "permitted_xp_host",
                "key_file",
                "producer_kind_filter",
            },
        )

    def test_dry_run_writes_nothing(self):
        database = FakeDatabase()
        self.assertFalse(register(database, self.plan()))
        self.assertEqual(database.writes, [])

    def test_only_target_device_and_server_are_written(self):
        database = FakeDatabase(
            devices=("existing/hardware/device",), servers=("Other/1",)
        )
        self.assertTrue(register(database, self.plan(), apply=True))
        self.assertEqual(len(database.writes), 3)
        self.assertEqual(
            database.writes[0], ("device", DEVICE, "DS_AcqTelemetry", SERVER)
        )
        self.assertEqual(database.writes[1][1], DEVICE)
        self.assertEqual(database.writes[2], ("server", SERVER, "everest", 1, 1))

    def test_case_insensitive_device_and_server_collisions_write_nothing(self):
        for database in (
            FakeDatabase(devices=(DEVICE.upper(),)),
            FakeDatabase(servers=(SERVER.upper(),)),
        ):
            with self.subTest(database=database):
                with self.assertRaisesRegex(RuntimeError, "Refusing to replace"):
                    register(database, self.plan(), apply=True)
                self.assertEqual(database.writes, [])

    def test_missing_or_invalid_key_fails_before_registration(self):
        with tempfile.TemporaryDirectory() as temporary:
            key = Path(temporary) / "missing.key"
            with self.assertRaises(FileNotFoundError):
                deployment_plan(key)
            key.write_bytes(b"short")
            with self.assertRaises(ValueError):
                deployment_plan(key)

    def test_starter_wrapper_does_not_launch_a_timed_soak_or_terminal_ui(self):
        wrapper = (
            Path(__file__).resolve().parents[2]
            / "DeviceServers"
            / "DS_AcqTelemetry.bat"
        )
        content = wrapper.read_text().lower()
        self.assertIn("run_logged_server.cmd", content)
        self.assertNotIn("--until", content)
        self.assertNotIn("run_acq_telemetry_soak.py", content)
        self.assertNotIn("launch_device_server.cmd", content)
        self.assertIn('if "%exit_code%"=="0" goto done', content)
        self.assertIn("timeout /t 5 /nobreak", content)
        self.assertIn("goto run", content)


if __name__ == "__main__":
    unittest.main()
