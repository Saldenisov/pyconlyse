import os
import shutil
import tempfile
import unittest

from elyse_agent.audit import AuditLog
from elyse_agent.channel_registry import ChannelRegistry
from elyse_agent.commands import CommandRouter
from elyse_agent.simulator import SimulatedBackend
from elyse_agent.state import AgentState


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        config = {
            "agent_name": "test",
            "mode": "simulation",
            "allow_hardware_writes": False,
        }
        registry = ChannelRegistry(os.path.join(ROOT, "data")).load()
        self.router = CommandRouter(
            SimulatedBackend(),
            AgentState(config),
            registry,
            AuditLog(os.path.join(self.temp_dir, "audit.jsonl")),
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_ping_and_idempotency(self):
        request = {"id": "a", "command": "ping", "params": {}}
        first = self.router.dispatch(request)
        second = self.router.dispatch(request)
        self.assertTrue(first["ok"])
        self.assertEqual(first, second)

    def test_request_id_reuse_with_different_command_is_rejected(self):
        self.router.dispatch({"id": "a", "command": "ping", "params": {}})
        result = self.router.dispatch({"id": "a", "command": "get_status", "params": {}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "command_error")

    def test_raw_hardware_write_command_is_not_exposed(self):
        result = self.router.dispatch({"id": "x", "command": "write", "params": {}})
        self.assertFalse(result["ok"])

    def test_simulated_output_command_changes_only_emulated_state(self):
        self.router.dispatch({"id": "init-out", "command": "initialize", "params": {}})
        write = self.router.dispatch(
            {
                "id": "set-out",
                "command": "set_simulated_digital_output",
                "params": {"task": "C3_DIO96_DO", "index": 9, "value": True},
            }
        )
        snapshot = self.router.dispatch(
            {"id": "snapshot-out", "command": "get_snapshot", "params": {}}
        )
        self.assertTrue(write["ok"])
        self.assertFalse(write["result"]["hardware_writes"])
        self.assertTrue(snapshot["result"]["digital_outputs"]["C3_DIO96_DO"][9])

    def test_simulation_lifecycle(self):
        initialized = self.router.dispatch(
            {"id": "init", "command": "initialize", "params": {}}
        )
        self.assertTrue(initialized["ok"])
        scenario = self.router.dispatch(
            {
                "id": "scenario",
                "command": "set_simulation_scenario",
                "params": {"name": "beam_ready"},
            }
        )
        self.assertTrue(scenario["ok"])
        snapshot = self.router.dispatch(
            {"id": "snapshot", "command": "get_snapshot", "params": {}}
        )
        self.assertEqual(snapshot["result"]["scenario"], "beam_ready")

    def test_psp_supervision_snapshot_command(self):
        self.router.dispatch({"id": "init-psp", "command": "initialize", "params": {}})
        result = self.router.dispatch(
            {"id": "psp", "command": "get_psp_snapshot", "params": {}}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["channel_count"], 472)
        self.assertEqual(
            result["result"]["payload_format"],
            "channel:value:source_timestamp",
        )
        self.assertFalse(result["result"]["hardware_writes"])


if __name__ == "__main__":
    unittest.main()
