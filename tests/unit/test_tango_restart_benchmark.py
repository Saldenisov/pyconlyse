import base64
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.refactor import benchmark_tango_restarts as benchmark
from scripts.refactor.verify_refactor import RefactorToolError


class TestTangoRestartBenchmark(unittest.TestCase):
    COMMIT = "a" * 40
    SERVERS = ("DS_DG645/main", "DS_HAMAMATSU_STREAK/main")

    def _write_approval(self, directory: Path, target: str = "everest") -> Path:
        path = directory / "restart-benchmark-approval.toml"
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat().replace(
            "+00:00", "Z"
        )
        path.write_text(
            "\n".join(
                (
                    f'commit = "{self.COMMIT}"',
                    'servers = ["DS_DG645/main", "DS_HAMAMATSU_STREAK/main"]',
                    'approver = "Lab operator"',
                    "hardware_safe = true",
                    f'expires_at_utc = "{expiry}"',
                    f'target = "{target}"',
                    "",
                )
            ),
            encoding="utf-8",
        )
        return path

    def test_targets_are_fixed_for_everest_and_elysium2(self):
        everest = benchmark.TANGO_RESTART_TARGETS["everest"]
        elysium2 = benchmark.TANGO_RESTART_TARGETS["elysium2"]
        self.assertEqual(everest.ssh_host, "elyse@10.20.30.202")
        self.assertEqual(everest.starter_device, "tango/admin/everest")
        self.assertEqual(elysium2.ssh_host, "elysium2")
        self.assertEqual(elysium2.repository, r"C:\dev\pyconlyse")
        self.assertEqual(elysium2.starter_device, "tango/admin/elysium2")

    def test_readiness_device_parser_binds_only_requested_servers(self):
        devices = benchmark.parse_readiness_devices(
            ["DS_DG645/main=sys/dg645/1"], self.SERVERS
        )
        self.assertEqual(devices, {"DS_DG645/main": "sys/dg645/1"})
        with self.assertRaisesRegex(RefactorToolError, "unrequested server"):
            benchmark.parse_readiness_devices(["DS_OTHER/main=sys/dg645/1"], self.SERVERS)
        with self.assertRaisesRegex(RefactorToolError, "Unsafe Tango readiness device"):
            benchmark.parse_readiness_devices(["DS_DG645/main=sys/dg645/1;whoami"], self.SERVERS)
        with self.assertRaisesRegex(RefactorToolError, "repeated"):
            benchmark.parse_readiness_devices(
                ["DS_DG645/main=sys/dg645/1", "DS_DG645/main=sys/dg645/2"], self.SERVERS
            )

    def test_duration_bounds_reject_polling_that_can_overload_starter(self):
        self.assertEqual(
            benchmark.validate_duration(0.10, name="poll interval", minimum=0.05, maximum=1.0),
            0.10,
        )
        with self.assertRaisesRegex(RefactorToolError, "poll interval"):
            benchmark.validate_duration(0.01, name="poll interval", minimum=0.05, maximum=1.0)

    def test_powershell_instruments_stop_launch_registration_readiness_and_failure(self):
        script = benchmark.build_benchmark_powershell(
            self.SERVERS,
            self.COMMIT,
            benchmark.TANGO_RESTART_TARGETS["everest"],
            readiness_devices={"DS_DG645/main": "sys/dg645/1"},
        )
        self.assertIn("time.monotonic_ns()", script)
        self.assertIn("'stop_request'", script)
        self.assertIn("'stop_confirmation'", script)
        self.assertIn("phase_prefix + '_request'", script)
        self.assertIn("phase_prefix + '_registration'", script)
        self.assertIn("'admin_readiness'", script)
        self.assertIn("'device_readiness'", script)
        self.assertIn("'recovery_start'", script)
        self.assertIn("starter.command_inout('DevGetRunningServers', True)", script)
        self.assertIn("starter.command_inout('DevGetStopServers', True)", script)
        self.assertIn("DeviceProxy(device).ping()", script)
        self.assertIn(benchmark.MEASUREMENT_PREFIX, script)
        self.assertIn("poll_interval_s = 0.1", script)
        self.assertIn("remote worktree is dirty", script)
        self.assertNotIn("HardKillServer", script)
        self.assertNotIn("taskkill", script)
        self.assertNotIn("PDU", script)

    def test_ssh_command_keeps_remote_payload_encoded(self):
        script = benchmark.build_benchmark_powershell(
            [self.SERVERS[0]], self.COMMIT, benchmark.TANGO_RESTART_TARGETS["elysium2"]
        )
        command = benchmark.build_ssh_command(
            benchmark.TANGO_RESTART_TARGETS["elysium2"].ssh_host, script
        )
        self.assertEqual(command[:2], ("ssh", "elysium2"))
        self.assertEqual(base64.b64decode(command[-1]).decode("utf-16le"), script)

    def test_parser_retains_remote_failure_measurement(self):
        line = benchmark.MEASUREMENT_PREFIX + json.dumps(
            {
                "schema_version": 1,
                "server": "DS_DG645/main",
                "outcome": "failed",
                "total_duration_ms": 701.2,
                "phases": {"start_registration": {"status": "timeout"}},
            }
        )
        records = benchmark.parse_measurements("status\n" + line + "\n")
        self.assertEqual(records[0]["outcome"], "failed")
        with self.assertRaisesRegex(RefactorToolError, "invalid measurement JSON"):
            benchmark.parse_measurements(benchmark.MEASUREMENT_PREFIX + "{")

    def test_generated_remote_probe_records_registration_and_readiness_with_fake_tango(self):
        server = self.SERVERS[0]
        script = benchmark.build_benchmark_powershell(
            [server], self.COMMIT, benchmark.TANGO_RESTART_TARGETS["everest"]
        )
        remote_code = script.split("$code = @'\n", 1)[1].split("\n'@\n", 1)[0]
        server_state = {"running": {server}, "stopped": set()}

        class FakeStarter:
            def command_inout(self, command, value):
                if command.startswith("DevGet") and value is not True:
                    raise AssertionError(f"Unexpected Starter query argument: {value!r}")
                if not command.startswith("DevGet") and value != server:
                    raise AssertionError(f"Unexpected Starter action argument: {value!r}")
                if command == "DevGetRunningServers":
                    return list(server_state["running"])
                if command == "DevGetStopServers":
                    return list(server_state["stopped"])
                if command == "DevStop":
                    server_state["running"].discard(value)
                    server_state["stopped"].add(value)
                    return None
                if command == "DevStart":
                    server_state["stopped"].discard(value)
                    server_state["running"].add(value)
                    return None
                raise AssertionError(f"Unexpected Starter command: {command}")

        class FakeReadyDevice:
            def ping(self):
                return 1

        starter = FakeStarter()

        def fake_device_proxy(name):
            if name == "tango/admin/everest":
                return starter
            if name == "dserver/" + server:
                return FakeReadyDevice()
            raise AssertionError(f"Unexpected Tango device: {name}")

        fake_tango = types.ModuleType("tango")
        fake_tango.DeviceProxy = fake_device_proxy
        output = io.StringIO()
        original_tango = sys.modules.get("tango")
        try:
            sys.modules["tango"] = fake_tango
            with redirect_stdout(output):
                exec(remote_code, {"__name__": "__benchmark_test__"})
        finally:
            if original_tango is None:
                sys.modules.pop("tango", None)
            else:
                sys.modules["tango"] = original_tango
        record = benchmark.parse_measurements(output.getvalue())[0]
        self.assertEqual(record["outcome"], "ok")
        self.assertEqual(
            set(record["phases"]),
            {
                "precheck",
                "stop_request",
                "stop_confirmation",
                "start_request",
                "start_registration",
                "admin_readiness",
            },
        )
        self.assertTrue(all(phase["duration_ms"] >= 0 for phase in record["phases"].values()))

    def test_generated_remote_probe_accepts_late_registration_after_devstart_error(self):
        server = self.SERVERS[0]
        script = benchmark.build_benchmark_powershell(
            [server], self.COMMIT, benchmark.TANGO_RESTART_TARGETS["everest"]
        )
        remote_code = script.split("$code = @'\n", 1)[1].split("\n'@\n", 1)[0]
        server_state = {"running": {server}, "stopped": set(), "start_calls": 0}

        class FakeStarter:
            def command_inout(self, command, value):
                if command == "DevGetRunningServers":
                    return list(server_state["running"])
                if command == "DevGetStopServers":
                    return list(server_state["stopped"])
                if command == "DevStop":
                    server_state["running"].discard(value)
                    server_state["stopped"].add(value)
                    return None
                if command == "DevStart":
                    server_state["start_calls"] += 1
                    server_state["stopped"].discard(value)
                    server_state["running"].add(value)
                    raise RuntimeError("AlreadyRunning after Starter accepted launch")
                raise AssertionError(f"Unexpected Starter command: {command}")

        class FakeReadyDevice:
            def ping(self):
                return 1

        starter = FakeStarter()
        fake_tango = types.ModuleType("tango")
        fake_tango.DeviceProxy = lambda name: (
            starter if name == "tango/admin/everest" else FakeReadyDevice()
        )
        output = io.StringIO()
        original_tango = sys.modules.get("tango")
        try:
            sys.modules["tango"] = fake_tango
            with redirect_stdout(output):
                exec(remote_code, {"__name__": "__benchmark_test__"})
        finally:
            if original_tango is None:
                sys.modules.pop("tango", None)
            else:
                sys.modules["tango"] = original_tango
        record = benchmark.parse_measurements(output.getvalue())[0]
        self.assertEqual(record["outcome"], "ok")
        self.assertEqual(record["phases"]["start_request"]["status"], "error")
        self.assertEqual(record["phases"]["start_registration"]["status"], "ok")
        self.assertEqual(server_state["start_calls"], 1)

    def test_generated_remote_probe_aborts_after_first_failure_and_preserves_later_server(self):
        first, second = self.SERVERS
        script = benchmark.build_benchmark_powershell(
            self.SERVERS, self.COMMIT, benchmark.TANGO_RESTART_TARGETS["everest"]
        )
        remote_code = script.split("$code = @'\n", 1)[1].split("\n'@\n", 1)[0]
        calls = []

        class FailingStarter:
            def command_inout(self, command, value):
                calls.append((command, value))
                if command == "DevGetRunningServers":
                    return [first, second]
                if command == "DevGetStopServers":
                    return []
                if command == "DevStop":
                    raise RuntimeError("simulated stop failure")
                raise AssertionError(f"Unexpected Starter command: {command}")

        fake_tango = types.ModuleType("tango")
        fake_tango.DeviceProxy = lambda _name: FailingStarter()
        output = io.StringIO()
        original_tango = sys.modules.get("tango")
        try:
            sys.modules["tango"] = fake_tango
            with redirect_stdout(output), self.assertRaisesRegex(RuntimeError, "benchmark failed"):
                exec(remote_code, {"__name__": "__benchmark_test__"})
        finally:
            if original_tango is None:
                sys.modules.pop("tango", None)
            else:
                sys.modules["tango"] = original_tango
        records = benchmark.parse_measurements(output.getvalue())
        self.assertEqual([record["server"] for record in records], [first])
        self.assertNotIn(("DevStop", second), calls)

    def test_report_has_success_failure_and_duration_summary(self):
        run = benchmark.BenchmarkRun(
            target="everest",
            expected_commit=self.COMMIT,
            returncode=1,
            stderr="remote failure",
            requested_servers=("a/b", "c/d"),
            measurements=(
                {"server": "a/b", "outcome": "ok", "total_duration_ms": 100.0},
                {"server": "c/d", "outcome": "failed", "total_duration_ms": 300.0},
            ),
        )
        report = benchmark.build_report(run)
        self.assertEqual(report["successful_servers"], 1)
        self.assertEqual(report["failed_servers"], 1)
        self.assertEqual(report["requested_server_count"], 2)
        self.assertEqual(report["total_duration_ms"], {"min": 100.0, "median": 200.0, "max": 300.0})
        self.assertEqual(report["transport_returncode"], 1)

    def test_report_keeps_requested_count_when_transport_fails_before_a_record(self):
        report = benchmark.build_report(
            benchmark.BenchmarkRun(
                target="elysium2",
                expected_commit=self.COMMIT,
                returncode=255,
                stderr="ssh: connect to host elysium2 failed",
                requested_servers=self.SERVERS,
                measurements=(),
            )
        )
        self.assertEqual(report["requested_server_count"], 2)
        self.assertEqual(report["server_count"], 0)
        self.assertEqual(report["failed_servers"], 0)
        self.assertEqual(report["transport_returncode"], 255)

    def test_output_must_be_external_json_and_is_parseable(self):
        report = {"schema_version": 1, "measurements": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "results.json"
            written = benchmark.write_report(output, report)
            self.assertEqual(json.loads(written.read_text(encoding="utf-8")), report)
            with self.assertRaisesRegex(RefactorToolError, "suffix"):
                benchmark.write_report(Path(temp_dir) / "results.txt", report)
        with self.assertRaisesRegex(RefactorToolError, "absolute"):
            benchmark.write_report("relative.json", report)

    def test_approval_requires_matching_target_binding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_approval(Path(temp_dir), target="elysium2")
            with self.assertRaisesRegex(RefactorToolError, "Approval target"):
                benchmark.load_benchmark_approval(
                    path,
                    self.COMMIT,
                    self.SERVERS,
                    benchmark.TANGO_RESTART_TARGETS["everest"],
                )

    def test_run_benchmark_parses_output_without_contacting_a_remote_host(self):
        measurement = {
            "schema_version": 1,
            "server": self.SERVERS[0],
            "outcome": "ok",
            "total_duration_ms": 123.4,
            "phases": {},
        }
        captured = {}

        def runner(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(
                argv,
                0,
                benchmark.MEASUREMENT_PREFIX + json.dumps(measurement) + "\n",
                "",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            approval = self._write_approval(Path(temp_dir))
            with redirect_stdout(io.StringIO()):
                run = benchmark.run_benchmark(
                    benchmark.TANGO_RESTART_TARGETS["everest"],
                    self.SERVERS,
                    self.COMMIT,
                    approval,
                    runner=runner,
                )
        self.assertEqual(run.returncode, 0)
        self.assertEqual(run.measurements, (measurement,))
        self.assertEqual(captured["argv"][:2], ("ssh", "elyse@10.20.30.202"))
        self.assertFalse(captured["kwargs"]["check"])
        self.assertTrue(captured["kwargs"]["capture_output"])

    def test_dry_run_never_calls_remote_runner(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = benchmark.main(
                [
                    "--target",
                    "everest",
                    "--server",
                    self.SERVERS[0],
                    "--expected-commit",
                    self.COMMIT,
                ]
            )
        self.assertEqual(result, 0)
        self.assertIn("Dry run", output.getvalue())
        self.assertIn("No Tango, SSH, or remote commands executed.", output.getvalue())

    def test_apply_requires_external_approval_and_report_path(self):
        with self.assertRaisesRegex(RefactorToolError, "approval-file"):
            benchmark.main(
                [
                    "--apply",
                    "--target",
                    "everest",
                    "--server",
                    self.SERVERS[0],
                    "--expected-commit",
                    self.COMMIT,
                ]
            )
        with self.assertRaisesRegex(RefactorToolError, "--output"):
            benchmark.main(
                [
                    "--apply",
                    "--target",
                    "everest",
                    "--server",
                    self.SERVERS[0],
                    "--expected-commit",
                    self.COMMIT,
                    "--approval-file",
                    "/tmp/unused.toml",
                ]
            )


if __name__ == "__main__":
    unittest.main()
