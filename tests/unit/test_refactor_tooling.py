import base64
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.refactor import deploy_everest, restart_tango_servers, verify_refactor


class TestRefactorTooling(unittest.TestCase):
    def test_verification_checks_unstaged_and_staged_tracked_diffs(self):
        commands = verify_refactor.build_verification_commands()
        argv = [command.argv for command in commands]
        self.assertIn(("git", "diff", "--check"), argv)
        self.assertIn(("git", "diff", "--cached", "--check"), argv)
        self.assertTrue(all(command.cwd == verify_refactor.PROJECT_ROOT for command in commands))

    def test_verification_includes_tests_in_compileall_and_ruff(self):
        commands = verify_refactor.build_verification_commands()
        argv = [command.argv for command in commands]
        compileall = next(command for command in argv if "compileall" in command)
        ruff = next(command for command in argv if "ruff" in command)
        self.assertIn("tests", compileall)
        self.assertEqual(ruff[:8], ("conda", "run", "-n", "pyconlyse39", "ruff", "check", "DeviceServers", "web/backend"))
        self.assertIn("tests", ruff)

    def test_full_verification_is_software_only_and_includes_frontend(self):
        commands = verify_refactor.build_verification_commands(full=True, include_frontend=True)
        argv = [command.argv for command in commands]
        self.assertIn(
            (
                "conda",
                "run",
                "-n",
                "pyconlyse39",
                "python",
                "-m",
                "pytest",
                "-m",
                "not slow and not integration and not netio",
            ),
            argv,
        )
        self.assertIn(("npm", "test", "--", "--watchAll=false"), argv)
        self.assertIn(("npm", "run", "build"), argv)

    def test_deploy_tests_exact_sha_in_detached_worktree_before_fast_forward(self):
        commit = "a" * 40
        script = deploy_everest.build_deploy_powershell("develop", commit)
        self.assertIn("function Invoke-Native", script)
        self.assertIn("$LASTEXITCODE", script)
        self.assertIn(f"git worktree add --detach -- $testWorktree {commit}", script)
        self.assertIn("python scripts/refactor/verify_refactor.py --apply --full", script)
        self.assertIn("git worktree remove --force -- $testWorktree", script)
        self.assertIn(f"git merge --ff-only {commit}", script)
        self.assertLess(
            script.index("python scripts/refactor/verify_refactor.py --apply --full"),
            script.index(f"git merge --ff-only {commit}"),
        )
        self.assertNotIn("reset --hard", script)
        self.assertNotIn("taskkill", script)
        self.assertNotIn("DevStart", script)

    def test_ssh_command_encodes_powershell_without_shell_interpolation(self):
        command = deploy_everest.build_ssh_command("elyse@10.20.30.202", "Write-Output 'ok'")
        self.assertEqual(command[:2], ("ssh", "elyse@10.20.30.202"))
        self.assertIn("-EncodedCommand", command)
        encoded = command[-1]
        self.assertEqual(base64.b64decode(encoded).decode("utf-16le"), "Write-Output 'ok'")

    def test_deploy_refuses_dirty_local_tree(self):
        def runner(argv, **_kwargs):
            if tuple(argv[:3]) == ("git", "status", "--porcelain"):
                return subprocess.CompletedProcess(argv, 0, " M web/frontend/src/PumpProbeV0.js\n", "")
            raise AssertionError(f"Unexpected command: {argv}")

        with self.assertRaisesRegex(verify_refactor.RefactorToolError, "worktree is dirty"):
            deploy_everest.assert_clean_local_tree(runner)

    def test_deploy_refuses_when_local_head_differs_from_origin(self):
        def runner(argv, **_kwargs):
            self.assertEqual(tuple(argv), ("git", "rev-parse", "HEAD"))
            return subprocess.CompletedProcess(argv, 0, "a" * 40 + "\n", "")

        with self.assertRaisesRegex(verify_refactor.RefactorToolError, "local HEAD"):
            deploy_everest.assert_local_head("b" * 40, runner)

    def _write_approval(self, directory: Path, *, commit: str, servers: list[str], expires_at: datetime, hardware_safe: bool = True) -> Path:
        approval = directory / "restart-approval.toml"
        approval.write_text(
            "\n".join(
                [
                    f'commit = "{commit}"',
                    "servers = [" + ", ".join(f'\"{server}\"' for server in servers) + "]",
                    'approver = "Lab operator"',
                    f"hardware_safe = {'true' if hardware_safe else 'false'}",
                    f'expires_at_utc = "{expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return approval

    def test_restart_accepts_external_approval_bound_to_commit_and_ordered_servers(self):
        commit = "b" * 40
        servers = ["DS_DG645/main", "DS_HAMAMATSU_STREAK/main"]
        with tempfile.TemporaryDirectory() as temp_dir:
            approval_path = self._write_approval(
                Path(temp_dir),
                commit=commit,
                servers=servers,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
            approval = restart_tango_servers.load_restart_approval(approval_path, commit, servers)
        self.assertEqual(approval.servers, tuple(servers))
        self.assertEqual(approval.approver, "Lab operator")

    def test_restart_rejects_approval_with_wrong_server_order_or_expiry(self):
        commit = "c" * 40
        servers = ["DS_DG645/main", "DS_HAMAMATSU_STREAK/main"]
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            approval_path = self._write_approval(
                temp_path,
                commit=commit,
                servers=list(reversed(servers)),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
            with self.assertRaisesRegex(verify_refactor.RefactorToolError, "ordered servers"):
                restart_tango_servers.load_restart_approval(approval_path, commit, servers)
            approval_path = self._write_approval(
                temp_path,
                commit=commit,
                servers=servers,
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            with self.assertRaisesRegex(verify_refactor.RefactorToolError, "expired"):
                restart_tango_servers.load_restart_approval(approval_path, commit, servers)

    def test_restart_rejects_repository_approval_and_missing_apply_approval_file(self):
        commit = "d" * 40
        repository_approval = verify_refactor.PROJECT_ROOT / "restart-approval.toml"
        with self.assertRaisesRegex(verify_refactor.RefactorToolError, "outside the repository"):
            restart_tango_servers.load_restart_approval(
                repository_approval, commit, ["DS_DG645/main"]
            )
        with self.assertRaisesRegex(verify_refactor.RefactorToolError, "approval-file"):
            restart_tango_servers.main(
                ["--apply", "--server", "DS_DG645/main", "--expected-commit", commit]
            )

    def test_restart_script_is_sequential_polls_both_lists_and_never_hard_kills(self):
        commit = "e" * 40
        script = restart_tango_servers.build_restart_powershell(
            ["DS_DG645/main", "DS_HAMAMATSU_STREAK/main"], commit
        )
        self.assertIn("starter.command_inout('DevGetRunningServers', True)", script)
        self.assertIn("starter.command_inout('DevGetStopServers', True)", script)
        self.assertIn("for server in servers:\n    restart_one(server)", script)
        self.assertIn("DEVSTART_RETRY_OK", script)
        self.assertIn("$LASTEXITCODE", script)
        self.assertNotIn("HardKillServer", script)
        self.assertNotIn("taskkill", script)
        self.assertNotIn("PDU", script)

    def test_invalid_server_names_are_rejected(self):
        with self.assertRaisesRegex(verify_refactor.RefactorToolError, "Unsafe Tango server"):
            verify_refactor.validate_servers(["DS/main; taskkill /f"])

    def test_scripts_run_directly_in_dry_run_mode(self):
        commands = [
            [sys.executable, "scripts/refactor/verify_refactor.py"],
            [sys.executable, "scripts/refactor/deploy_everest.py", "--branch", "develop"],
            [
                sys.executable,
                "scripts/refactor/restart_tango_servers.py",
                "--server",
                "DS_DG645/main",
                "--expected-commit",
                "f" * 40,
            ],
        ]
        for command in commands:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Dry run", completed.stdout)


if __name__ == "__main__":
    unittest.main()
