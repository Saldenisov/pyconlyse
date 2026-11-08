import os
import shutil
import socket
import tempfile
import threading
import unittest

from elyse_agent.audit import AuditLog
from elyse_agent.channel_registry import ChannelRegistry
from elyse_agent.commands import CommandRouter
from elyse_agent.protocol import recv_message, send_message
from elyse_agent.service import AgentServer
from elyse_agent.simulator import SimulatedBackend
from elyse_agent.state import AgentState


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ServiceTests(unittest.TestCase):
    def test_tcp_round_trip(self):
        temp_dir = tempfile.mkdtemp()
        config = {
            "agent_name": "test",
            "mode": "simulation",
            "allow_hardware_writes": False,
            "allow_input_task_creation": False,
        }
        registry = ChannelRegistry(os.path.join(ROOT, "data")).load()
        router = CommandRouter(
            SimulatedBackend(),
            AgentState(config),
            registry,
            AuditLog(os.path.join(temp_dir, "audit.jsonl")),
        )
        server = AgentServer(("127.0.0.1", 0), router, 1048576, 2.0)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        try:
            sock = socket.create_connection(server.server_address, timeout=2.0)
            try:
                send_message(sock, {"id": "round-trip", "command": "ping", "params": {}})
                response = recv_message(sock, 1048576)
                send_message(
                    sock,
                    {"id": "initialize", "command": "initialize", "params": {}},
                )
                initialized = recv_message(sock, 1048576)
                send_message(
                    sock,
                    {"id": "snapshot", "command": "get_snapshot", "params": {}},
                )
                snapshot = recv_message(sock, 1048576)
            finally:
                sock.close()
            self.assertTrue(response["ok"])
            self.assertEqual(response["result"]["reply"], "pong")
            self.assertTrue(initialized["ok"])
            self.assertEqual(snapshot["result"]["acquisition_state"], "READY")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2.0)
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
