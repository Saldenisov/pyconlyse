"""Complete synthetic 27-bank XML -> latest relay -> Everest RAM lane."""

import copy
import socket
import struct
import threading
import unittest
from unittest.mock import patch

from DeviceServers.control.elyse_acq.telemetry_sink import (
    TelemetrySinkServer,
    TelemetrySinkStore,
)
from legacy.xp_acq_agent.elyse_agent.protocol import recv_message
from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS, SharedStateStore
from legacy.xp_acq_agent.elyse_agent.shared_state_receiver import SharedStateServer
from legacy.xp_acq_agent.elyse_agent.telemetry_relay import TelemetryRelay, sign

KEY = b"fixture-key-not-a-production-secret-0123456789"


def xml_fixture(sequence):
    records = []
    for index, name in enumerate(BANKS):
        error = 17 if index == 2 else 0
        records.append(
            "<Cluster><Name></Name><NumElts>3</NumElts>"
            "<String><Name>bank</Name><Val>{}</Val></String>"
            "<LvVariant><Name>value</Name><U32><Name>fixture</Name><Val>{}</Val></U32></LvVariant>"
            "<Cluster><Name>error</Name><NumElts>3</NumElts>"
            "<Boolean><Name>status</Name><Val>{}</Val></Boolean>"
            "<I32><Name>code</Name><Val>{}</Val></I32>"
            "<String><Name>source</Name><Val>fixture error source</Val></String>"
            "</Cluster></Cluster>".format(
                name, sequence + index, int(bool(error)), error
            )
        )
    return (
        "<LvVariant><Name></Name><Array><Name></Name><Dimsize>27</Dimsize>"
        + "".join(records)
        + "</Array></LvVariant>"
    ).encode("utf-8")


def signed(body):
    value = dict(body=body, nonce="a" * 32)
    return dict(value, signature=sign(KEY, "ACQ-TELEMETRY-REQUEST-1", value))


class SnapshotTransportTests(unittest.TestCase):
    def test_xml_loopback_signed_relay_all_27_latest_values_without_history(self):
        xp_store = SharedStateStore("fixture")
        sink_store = TelemetrySinkStore(KEY, permitted_producer_kind="fixture")
        xp_server = SharedStateServer(("127.0.0.1", 0), xp_store)
        sink_server = TelemetrySinkServer(
            ("127.0.0.1", 0), sink_store, permitted_peers=("127.0.0.1",)
        )
        threads = [
            threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.01}
            )
            for server in (xp_server, sink_server)
        ]
        for thread in threads:
            thread.start()
        try:
            relay = TelemetryRelay(xp_store.outbox, sink_server.server_address, KEY)
            with patch(
                "sqlite3.connect", side_effect=AssertionError("SQLite forbidden")
            ):
                for iteration in range(3):
                    raw = xml_fixture(iteration)
                    with socket.create_connection(
                        xp_server.server_address, timeout=2
                    ) as connection:
                        connection.sendall(struct.pack("!I", len(raw)) + raw)
                        ack = recv_message(connection, 262144)
                    self.assertTrue(ack["ok"])
                    self.assertTrue(relay.send_once())
                    snapshot = sink_store.snapshot()
                    self.assertEqual(set(snapshot["publications"]), set(BANKS))
                    self.assertFalse(snapshot["missing_publications"])
                    for index, name in enumerate(BANKS):
                        self.assertEqual(
                            snapshot["publications"][name]["data"], iteration + index
                        )
                    self.assertTrue(
                        snapshot["publications"][BANKS[2]]["error"]["status"]
                    )
                    self.assertEqual(
                        snapshot["publications"][BANKS[2]]["error"]["code"], 17
                    )
                self.assertEqual(snapshot["received_this_process"], 3)
                self.assertFalse(snapshot["history_available"])
                self.assertEqual(xp_store.outbox.status()["everest_acknowledged"], 3)
        finally:
            for server in (xp_server, sink_server):
                server.shutdown()
            for thread in threads:
                thread.join(3)
            for server in (xp_server, sink_server):
                server.server_close()
            sink_store.close()

    def test_lost_ack_keeps_exact_retry_while_newest_pending_replaces_backlog(self):
        xp = SharedStateStore("fixture")
        sink = TelemetrySinkStore(KEY)
        xp.ingest(xml_fixture(0), "127.0.0.1")
        first = xp.outbox.peek()
        sink.accept(
            signed(first)
        )  # ACK lost deliberately; sender still retains in-flight ID.
        for iteration in range(1, 101):
            xp.ingest(xml_fixture(iteration), "127.0.0.1")
        self.assertEqual(xp.outbox.status()["pending"], 2)
        duplicate = sink.accept(signed(xp.outbox.peek()))
        self.assertTrue(duplicate["body"]["duplicate"])
        xp.outbox.acknowledge(first["relay_id"], first["message_id"])
        newest = xp.outbox.peek()
        self.assertEqual(newest["message_id"], first["message_id"] + 1)
        self.assertTrue(sink.accept(signed(newest))["body"]["accepted"])
        self.assertEqual(sink.snapshot()["publications"][BANKS[0]]["data"], 100)
        self.assertEqual(sink.snapshot()["received_this_process"], 2)
        sink.close()

    def test_invalid_bank_or_filter_cannot_commit_partial_snapshot(self):
        xp = SharedStateStore("fixture")
        xp.ingest(xml_fixture(0), "127.0.0.1")
        body = xp.outbox.peek()
        for mutate in (
            lambda value: value["packet"]["data"]["banks"].pop(),
            lambda value: value["packet"].update(producer_kind="copied_acquisition"),
        ):
            sink = TelemetrySinkStore(KEY, permitted_producer_kind="fixture")
            invalid = copy.deepcopy(body)
            mutate(invalid)
            with self.assertRaises(Exception):
                sink.accept(signed(invalid))
            self.assertEqual(sink.snapshot()["received_this_process"], 0)
            self.assertEqual(sink.snapshot()["publications"], {})
            sink.close()


if __name__ == "__main__":
    unittest.main()
