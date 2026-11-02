"""Live-frame replacement and signed ACK integration, Python 3.4, no hardware."""
import socket
import threading
import unittest
import importlib.machinery
import os

from legacy.xp_acq_control.elyse_agent.camera_latest import LatestCameraFrameQueue
from legacy.xp_acq_control.elyse_agent.camera_stream import CameraFrameReceiver, CameraFrameSender
from legacy.xp_acq_control.elyse_agent.camera_stream_publisher import CameraStreamPublisher
from tests.unit.test_camera_stream import KEY, metadata
from tests.unit.test_supervision_camera_stream_publisher import configuration
from tests.unit.test_supervision_vi_telemetry import image


class LatestCameraTests(unittest.TestCase):
    def test_burst_retains_only_newest_owned_frame_without_transport_id_gaps(self):
        now = [1.]
        queue = LatestCameraFrameQueue(clock=lambda: now[0])
        for sequence in range(1, 1001):
            frame = metadata(sequence)
            self.assertTrue(queue.enqueue(frame, b'abcd'))
        frame['channel'] = 9
        now[0] = 2.
        message, value, pixels = queue.peek()
        self.assertEqual((message, value['sequence'], value['channel'], pixels), (1, 1000, 2, b'abcd'))
        self.assertAlmostEqual(value['source_age_seconds'], 1.001)
        self.assertEqual(queue.status()['replaced_pending'], 999)
        self.assertEqual(queue.status()['pending_bytes'], 4)
        queue.acknowledge(message)
        self.assertIsNone(queue.peek())
        self.assertFalse(queue.changed.is_set())

    def test_inflight_is_pinned_while_waiting_frames_are_replaced(self):
        queue = LatestCameraFrameQueue()
        queue.enqueue(metadata(1), b'abcd')
        first = queue.peek()
        for sequence in range(2, 1001):
            queue.enqueue(metadata(sequence), b'efgh')
        self.assertEqual(queue.peek()[0], first[0])
        self.assertEqual(queue.peek()[1]['sequence'], 1)
        self.assertEqual(queue.status()['pending'], 2)
        self.assertEqual(queue.status()['pending_bytes'], 8)
        for bad in (2, True):
            self.assertRaises(ValueError, queue.acknowledge, bad)
        queue.acknowledge(1)
        message, value, pixels = queue.peek()
        self.assertEqual((message, value['sequence'], pixels), (2, 1000, b'efgh'))
        queue.acknowledge(2)
        self.assertIsNone(queue.peek())

    def test_each_channel_has_its_own_latest_and_busy_channel_cannot_starve_other(self):
        queue = LatestCameraFrameQueue(capacity=2)
        queue.enqueue(metadata(1), b'abcd')
        queue.enqueue(dict(metadata(1), channel=3), b'efgh')
        queue.enqueue(metadata(2), b'ijkl')
        first = queue.peek()
        self.assertEqual((first[1]['channel'], first[1]['sequence']), (3, 1))
        queue.enqueue(dict(metadata(2), channel=3), b'mnop')
        queue.acknowledge(first[0])
        second = queue.peek()
        self.assertEqual((second[1]['channel'], second[1]['sequence']), (2, 2))
        queue.acknowledge(second[0])
        self.assertEqual(queue.peek()[1]['channel'], 3)

    def test_total_bytes_include_inflight_and_capacity_evictions_are_counted(self):
        queue = LatestCameraFrameQueue(capacity=1, max_bytes=8)
        queue.enqueue(metadata(1), b'abcd')
        queue.peek()
        queue.enqueue(metadata(2), b'efgh')
        queue.enqueue(dict(metadata(3), channel=3), b'ijkl')
        self.assertEqual(queue.status()['pending_bytes'], 8)
        self.assertEqual(queue.status()['replaced_pending'], 1)
        self.assertFalse(queue.enqueue(metadata(4, width=3, height=2), b'xxxxxx'))
        self.assertEqual(queue.status()['rejected_new'], 1)
        queue.acknowledge(1)
        self.assertEqual(queue.peek()[1]['channel'], 3)

    def test_lost_ack_retries_same_frame_then_sends_latest_with_contiguous_ids(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(2)
        listener.settimeout(3)
        self.addCleanup(listener.close)
        seen, failures = [], []
        receiver = CameraFrameReceiver(KEY, lambda frame, raw: seen.append(frame['sequence']))
        queue = LatestCameraFrameQueue()
        queue.enqueue(metadata(1), b'abcd')

        class LoseAck(object):
            def __init__(self, connection):
                self.connection = connection
            def recv(self, size):
                return self.connection.recv(size)
            def sendall(self, data):
                pass

        def receive():
            try:
                with listener.accept()[0] as connection:
                    connection.settimeout(3)
                    receiver.receive_once(LoseAck(connection))
                with listener.accept()[0] as connection:
                    connection.settimeout(3)
                    receiver.receive_once(connection)
                    receiver.receive_once(connection)
            except Exception as error:
                failures.append(error)

        worker = threading.Thread(target=receive)
        worker.start()
        sender = CameraFrameSender(queue, listener.getsockname(), KEY, timeout=1.)
        try:
            self.assertRaises(EOFError, sender.send_once)
            for sequence in range(2, 26):
                queue.enqueue(metadata(sequence), b'efgh')
            self.assertTrue(sender.send_once())
            self.assertTrue(sender.send_once())
            self.assertFalse(sender.send_once())
        finally:
            sender.disconnect()
            worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(seen, [1, 25])
        self.assertEqual(receiver.duplicates, 1)
        self.assertEqual(queue.status()['acknowledged'], 2)

    def test_stalled_receiver_does_not_hold_producer_lock(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(3)
        self.addCleanup(listener.close)
        entered, release, produced = threading.Event(), threading.Event(), threading.Event()
        failures = []
        queue = LatestCameraFrameQueue()
        queue.enqueue(metadata(1), b'abcd')
        def consume(frame, pixels):
            entered.set()
            if not release.wait(2):
                raise RuntimeError('Test ACK gate timed out')
        receiver = CameraFrameReceiver(KEY, consume)
        def receive():
            try:
                with listener.accept()[0] as connection:
                    receiver.receive_once(connection)
            except Exception as error:
                failures.append(error)
        sender = CameraFrameSender(queue, listener.getsockname(), KEY, timeout=3.)
        def send():
            try:
                sender.send_once()
            except Exception as error:
                failures.append(error)
        def produce():
            for sequence in range(2, 1001):
                queue.enqueue(metadata(sequence), b'efgh')
            produced.set()
        receiving, sending, producing = [threading.Thread(target=target) for target in (receive, send, produce)]
        receiving.start()
        sending.start()
        try:
            self.assertTrue(entered.wait(1))
            producing.start()
            self.assertTrue(produced.wait(1), 'Producer waited for network ACK')
            self.assertEqual(queue.status()['pending'], 2)
        finally:
            release.set()
            for worker in (producing, sending, receiving):
                if worker.ident is not None:
                    worker.join(4)
            sender.disconnect()
        self.assertEqual(failures, [])
        self.assertEqual(queue.peek()[1]['sequence'], 1000)


class LatestPublisherTests(unittest.TestCase):
    def publisher(self, **changes):
        config = configuration(delivery_policy='latest', **changes)
        publisher = CameraStreamPublisher(config, KEY, clock=lambda: 1.)
        self.addCleanup(publisher.close)
        return publisher

    def test_latest_staging_and_transport_coalesce_without_decoding_inline(self):
        publisher = self.publisher()
        for sequence in range(1, 101):
            publisher.submit_video(image(sequence), 1.)
        self.assertEqual(publisher.status()['staging']['pending'], 1)
        self.assertEqual(publisher.status()['staging']['replaced_pending'], 99)
        publisher.process_once()
        message, frame, pixels = publisher.queue.peek()
        self.assertEqual((message, frame['sequence']), (1, 100))
        for sequence in range(101, 201):
            publisher.submit_video(image(sequence), 1.)
            publisher.process_once()
        self.assertEqual(publisher.queue.peek()[1]['sequence'], 100)
        publisher.queue.acknowledge(message)
        self.assertEqual(publisher.queue.peek()[1]['sequence'], 200)
        self.assertEqual(publisher.status()['fifo']['replaced_pending'], 99)
        self.assertEqual(publisher.status()['staging']['errors'], 0)

    def test_staging_keeps_latest_for_each_channel(self):
        publisher = self.publisher()
        for sequence in range(1, 11):
            for channel in (2, 3):
                publisher.submit_video(dict(image(sequence), channel=channel), 1.)
        self.assertEqual(publisher.status()['staging']['pending'], 2)
        while publisher.process_once():
            pass
        result = []
        while publisher.queue.peek():
            message, frame, pixels = publisher.queue.peek()
            result.append((frame['channel'], frame['sequence']))
            publisher.queue.acknowledge(message)
        self.assertEqual(result, [(2, 10), (3, 10)])

    def test_invalid_policy_is_rejected_and_disabled_legacy_configs_remain_valid(self):
        for policy in ('lifo', None, True):
            self.assertRaises(ValueError, CameraStreamPublisher,
                              configuration(delivery_policy=policy), KEY)

    def test_installation_changes_only_camera_delivery_policy(self):
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..',
                                           'tools', 'install_supervision_camera_latest.pyw'))
        installer = importlib.machinery.SourceFileLoader('latest_camera_installer_test', path).load_module()
        original = dict(camera_stream=configuration(), vi_passive_shadow=False,
                        remote_control_enabled=True, ownership='retained',
                        synchronization=dict(values=[2175., 100.]))
        updated = installer.latest_configuration(original)
        self.assertNotIn('delivery_policy', original['camera_stream'])
        self.assertEqual(updated['camera_stream'].pop('delivery_policy'), 'latest')
        self.assertEqual(updated, original)
        self.assertRaises(RuntimeError, installer.latest_configuration,
                          dict(camera_stream=configuration(host='127.0.0.1')))


if __name__ == '__main__':
    unittest.main()
