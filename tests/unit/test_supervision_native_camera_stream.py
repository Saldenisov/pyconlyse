"""Private RAM card children/loopback; no NI, XP or live DB/services. Python3.4."""
import socket
import threading
import time
import unittest
from unittest.mock import patch

from legacy.xp_acq_control.elyse_agent.supervision_runtime import SupervisionRuntime
from legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry import SupervisionTelemetryPublisher
from legacy.xp_acq_control.elyse_agent.camera_stream_publisher import CameraStreamPublisher
from legacy.xp_acq_control.elyse_agent.camera_stream import CameraFrameReceiver
from tests.unit.test_supervision_camera_stream_publisher import configuration
from tests.unit.test_supervision_vi_telemetry import KEYS, image


class NativeCameraStreamTests(unittest.TestCase):
    def setUp(self):
        self.runtime = SupervisionRuntime(identity=dict(runtime_protocol_version=2,
            session_id='a' * 32, build_id='b' * 64), remote_enabled=True,
            counter_timing_controls_verified=True, period=.2,
            trusted_service_options=dict(
                sync=dict(trusted_factory='tests.unit.test_supervision_runtime:ram_sync_adapter'),
                video=dict(trusted_factory='tests.unit.test_supervision_runtime:ram_video_adapter')))
        self.publisher = SupervisionTelemetryPublisher(self.runtime, ('127.0.0.1', 12345),
            KEYS['supervision'], camera_stream_configuration=configuration(source_mode='VI_OR_NATIVE'))
        self.runtime.telemetry_publisher = self.publisher

    def tearDown(self):
        runtime = self.runtime
        try:
            if runtime._thread is not None:
                self.wait(lambda: runtime.snapshot()['current_operation'] is None)
                runtime.request_shutdown(electrical_off_confirmed=True)
                self.assertTrue(runtime.join(15))
        finally:
            # Only this test's known RAM descendants, never a live NI owner.
            for endpoint in runtime._owners.values():
                process = getattr(getattr(endpoint, 'client', None), '_process', None)
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(5)
            self.publisher.close()

    def wait(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.01)
        self.fail('RAM native-camera fixture deadline exceeded')

    def initialize(self):
        self.runtime.start()
        self.runtime.initialize(startup_confirmed=True)
        self.wait(lambda: self.runtime.snapshot()['state'] == 'RUNNING')
        self.wait(lambda: self.publisher.camera_stream.status()['staging']['python_frames_accepted'] >= 3)

    def test_returned_native_frames_use_fifo_before_any_owner_publication(self):
        with patch('legacy.xp_acq_control.elyse_agent.camera_stream.zlib.compress',
                   side_effect=AssertionError('Compression ran during capture')):
            self.initialize()
        self.assertEqual(self.publisher.sequence, 0)
        self.assertIsNone(self.publisher.camera_stream.sender.thread)
        self.assertTrue(self.runtime._owners['video'].continuous_input)
        self.assertFalse(self.runtime._owners['sync'].continuous_input)
        self.assertIsNone(self.publisher.status()['native_video_period_seconds'])
        stream = self.publisher.camera_stream
        self.assertTrue(stream.process_once())
        message, meta, pixels = stream.queue.peek()
        self.assertEqual(pixels, bytes(range(6)))
        self.assertEqual(meta['source_session_id'], 'a' * 32)
        self.assertEqual(meta['capture_session_id'],
            self.runtime._owners['video'].status()['native']['worker_generation'])
        self.assertGreater(meta['sequence'], 0)
        self.assertGreaterEqual(meta['source_age_seconds'], 0)
        # Metadata publication must not encode/send a duplicate image at 1Hz.
        with patch.object(self.runtime, 'video_frame_snapshot',
                          side_effect=AssertionError('Sampled camera path used')):
            self.assertTrue(self.publisher.publish_once())
        packet = self.publisher.outbox.peek()['packet']
        self.assertEqual(packet['source_mode'], 'PYTHON_NATIVE')
        self.assertIsNone(packet['video_frame'])

    def test_full_or_failed_staging_does_not_fault_card_or_stop_sync(self):
        self.publisher.close()
        self.publisher = SupervisionTelemetryPublisher(self.runtime, ('127.0.0.1', 12345),
            KEYS['supervision'], camera_stream_configuration=configuration(source_mode='VI_OR_NATIVE', capacity=1))
        self.runtime.telemetry_publisher = self.publisher
        self.runtime.start()
        self.runtime.initialize(startup_confirmed=True)
        self.wait(lambda: self.runtime._owners.get('video') is not None
                  and self.runtime._owners['video'].status()['sample_sink']['rejected'] >= 3)
        self.wait(lambda: self.runtime.snapshot()['state'] == 'RUNNING')
        endpoint = self.runtime._owners['video']
        with patch.object(self.publisher, 'offer_native_video', side_effect=IOError('injected staging failure')):
            self.wait(lambda: endpoint.status()['sample_sink']['errors'] >= 2)
        state = endpoint.status()
        self.assertEqual(state['state'], 'READY')
        self.assertTrue(state['input_current'])
        self.assertEqual(state['input_error'], '')
        self.assertEqual(self.runtime._owners['sync'].status()['state'], 'READY')
        self.assertEqual(self.publisher.camera_stream.status()['staging']['pending'], 1)

    def test_native_samples_reach_receiver_with_matching_acks_on_one_connection(self):
        self.initialize()
        stream = self.publisher.camera_stream
        for unused in range(3):
            self.assertTrue(stream.process_once())
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(3.)
        seen, failures = [], []
        receiver = CameraFrameReceiver(KEYS['supervision'], lambda meta, pixels: seen.append((meta, pixels)))
        def receive():
            try:
                with listener.accept()[0] as connection:
                    connection.settimeout(3.)
                    for unused in range(3):
                        receiver.receive_once(connection)
            except Exception as error:
                failures.append(error)
        worker = threading.Thread(target=receive)
        worker.daemon = True
        worker.start()
        # The production configuration is never used as a socket target.
        stream.sender.address = listener.getsockname()
        try:
            for unused in range(3):
                self.assertTrue(stream.sender.send_once())
        finally:
            stream.sender.disconnect()
            worker.join(4.)
            listener.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(seen), 3)
        sequences = [meta['sequence'] for meta, pixels in seen]
        self.assertEqual(sequences, sorted(set(sequences)))
        self.assertTrue(all(meta['source_session_id'] == 'a' * 32 and pixels == bytes(range(6))
                            for meta, pixels in seen))
        self.assertEqual(stream.queue.status()['acknowledged'], 3)

    def test_sync_command_does_not_block_native_camera_admission(self):
        self.initialize()
        self.wait(lambda: self.runtime.counter_memory_part() is not None)
        self.runtime.dispatch_remote('counter_timing.set', dict(counter=2, delay_us=10., width_us=20.))
        self.wait(lambda: self.runtime.snapshot()['state'] == 'EXECUTING')
        before = self.publisher.camera_stream.status()['staging']['python_frames_accepted']
        self.publisher.camera_stream.process_once()  # Free a slot if the offline FIFO filled.
        self.wait(lambda: self.publisher.camera_stream.status()['staging']['python_frames_accepted'] > before)
        self.wait(lambda: self.runtime.snapshot()['state'] == 'RUNNING')
        self.wait(lambda: self.runtime.counter_memory_part() is not None)
        values = self.runtime.counter_memory_part()['values']
        self.assertEqual(values[4:6], [10., 20.])

    def test_retired_endpoint_cannot_stage_after_lifecycle_changes(self):
        self.initialize()
        endpoint = self.runtime._owners['video']
        sample = endpoint.status()['sample']
        with self.runtime._lock:
            self.runtime._operation = 'close'
            self.assertFalse(self.runtime._native_video_sample(endpoint, sample, time.monotonic()))
            self.runtime._operation = None
            actual = self.runtime._owners.pop('video')
            try:
                self.assertFalse(self.runtime._native_video_sample(endpoint, sample, time.monotonic()))
            finally:
                self.runtime._owners['video'] = actual

    def test_legacy_vi_stream_config_does_not_enable_native_fast_path(self):
        legacy = CameraStreamPublisher(configuration(), KEYS['supervision'])
        try:
            video = image()
            video['source'] = 'python_supervision_ni1409'
            self.assertRaises(ValueError, legacy.submit_python_video, video, 'a' * 32, 0.)
        finally:
            legacy.close()


if __name__ == '__main__':
    unittest.main()
