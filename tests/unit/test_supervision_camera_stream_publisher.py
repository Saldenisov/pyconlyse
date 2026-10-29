"""Future typed-VI stream wiring; Python3.4, no socket/VI/NI operations."""
import copy
import threading
import unittest
from unittest.mock import patch

from legacy.xp_acq_control.elyse_agent.supervision_gui import (
    BUTTON_LABELS, default_supervision_configuration, validate_supervision_configuration)
from legacy.xp_acq_control.elyse_agent.supervision_runtime import SupervisionRuntime
from legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry import SupervisionTelemetryPublisher
from legacy.xp_acq_control.elyse_agent.camera_stream_publisher import (
    CameraStreamPublisher, validate_camera_stream_configuration)
from tests.unit.test_supervision_vi_telemetry import (KEYS, image, observation, encoded, part,
    native_camera, native_timestamp, NATIVE_NOW, decode_vi_camera_binary)


def configuration(**changes):
    result = dict(enabled=True, source_mode='LABVIEW_BRIDGE', host='10.20.30.202', port=8769,
        every_n=1, capacity=128, max_bytes=64 * 1024 * 1024, max_channels=2,
        timeout_seconds=2., retry_seconds=.1)
    result.update(changes)
    return result


class SupervisionCameraStreamTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.runtime = SupervisionRuntime(identity=dict(runtime_protocol_version=2,
            session_id='a' * 32, build_id='c' * 64), clock=lambda: self.now)
        self.publisher = SupervisionTelemetryPublisher(self.runtime, ('127.0.0.1', 12345),
            KEYS['supervision'], clock=lambda: self.now, camera_stream_configuration=configuration())
        self.runtime.telemetry_publisher = self.publisher

    def tearDown(self):
        self.publisher.close()

    def submit(self, seq, video=None, counter=None):
        return self.publisher.ingest_observation(encoded(observation(seq, counter=counter,
            video=video if video is not None else image(seq))), '127.0.0.1')

    def drain(self):
        while self.publisher.camera_stream.process_once():
            pass

    def native(self, seq, size=768 * 576):
        self.now = seq / 25.
        self.publisher.wall_clock = lambda: NATIVE_NOW + self.now
        self.publisher.tick_clock = lambda: 100125 + int(self.now * 1000)
        observed = NATIVE_NOW + self.now - .125
        whole = int(observed)
        return native_camera(frame_count=seq, rows=1, columns=size, pixels=b'x' * size,
            observed=native_timestamp(whole, int((observed - whole) * (1 << 64))),
            observed_tick=100000 + int(self.now * 1000))

    def source_frames(self):
        values = []
        queue = self.publisher.camera_stream.queue
        while queue.peek():
            message, metadata, pixels = queue.peek()
            values.append((metadata, pixels))
            queue.acknowledge(message)
        return values

    def test_rapid_vi_frames_use_independent_fifo_not_one_second_owner_budget(self):
        for seq in range(1, 26):
            self.now = seq / 25.
            receipt = self.submit(seq, counter=part())
            self.assertIs(receipt['accepted'], True)
            self.assertIs(receipt['independent_camera_staged'], True)
        owner = self.publisher.outbox.peek()['packet']
        self.assertIsNone(owner['video_frame'])
        self.assertEqual(owner['counter_part']['values'], part()['values'])
        self.assertEqual([bank['publication'] for bank in owner['banks']], ['C12NI1409'])
        self.drain()
        frames = self.source_frames()
        self.assertEqual([meta['sequence'] for meta, pixels in frames], list(range(1, 26)))
        self.assertTrue(all(meta['source_session_id'] == 'b' * 32 and pixels == b'xxxx'
                            for meta, pixels in frames))
        self.assertIsNone(self.publisher.camera_stream.sender.thread)
        self.assertIsNone(self.runtime._thread)
        self.assertIsNone(self.publisher.status()['raw_video_period_seconds'])

    def test_native_pixels_never_take_a_base64_roundtrip_or_compress_during_receipt(self):
        raw = self.native(1)
        with patch('base64.b64encode', side_effect=AssertionError('Native pixels encoded')):
            with patch('base64.b64decode', side_effect=AssertionError('Native pixels decoded')):
                with patch('legacy.xp_acq_control.elyse_agent.camera_stream.zlib.compress',
                           side_effect=AssertionError('Compression ran in admission')):
                    result = self.publisher.ingest_observation(raw, '127.0.0.1')
                    self.drain()
        self.assertTrue(result['independent_camera_staged'])
        frames = self.source_frames()
        self.assertEqual(frames[0][1], b'x' * (768 * 576))
        self.assertEqual(frames[0][0]['sequence'], 2)
        self.assertEqual(self.publisher.camera_stream.status()['staging']['native_pixels_accepted'], 1)
        self.assertIsNone(self.publisher.outbox.peek()['packet']['video_frame'])

    def test_repeated_camera_receipts_do_not_build_27_bank_packets(self):
        self.publisher.ingest_observation(self.native(1), '127.0.0.1')
        old_publication = self.publisher.sequence
        with patch('legacy.xp_acq_control.elyse_agent.supervision_vi_telemetry.standard_packet',
                   side_effect=AssertionError('27 banks built on image receipt')):
            for seq in range(2, 6):
                self.publisher.ingest_observation(self.native(seq), '127.0.0.1')
        self.assertEqual(self.publisher.typed_accepted, 5)
        self.assertEqual(self.publisher.sequence, old_publication)
        self.assertTrue(self.publisher.publish_once())
        self.assertGreater(self.publisher.sequence, old_publication)
        self.drain()
        self.assertEqual(len(self.source_frames()), 5)

    def test_native_and_equivalent_json_retry_share_immutable_observation_identity(self):
        raw = self.native(1)
        self.publisher.ingest_observation(raw, '127.0.0.1')
        video = decode_vi_camera_binary(raw, NATIVE_NOW + self.now, 100125 + int(self.now * 1000))
        result = self.publisher.ingest_observation(encoded(video), '127.0.0.1')
        self.assertTrue(result['duplicate'])
        self.drain()
        self.assertEqual(len(self.source_frames()), 1)

    def test_native_bounds_and_clock_failures_are_not_deferred_to_stage(self):
        raw = self.native(1)
        self.publisher.wall_clock = lambda: NATIVE_NOW - 1
        self.assertRaises(ValueError, self.publisher.ingest_observation, raw, '127.0.0.1')
        self.publisher.wall_clock = lambda: NATIVE_NOW + self.now
        self.assertRaises(ValueError, self.publisher.ingest_observation, raw + b'x', '127.0.0.1')
        self.assertEqual(self.publisher.camera_stream.status()['staging']['accepted'], 0)

    def test_native_queue_preserves_real_age_and_bounds_owned_pixels(self):
        self.publisher.ingest_observation(self.native(1), '127.0.0.1')
        self.now += .5
        self.drain()
        metadata, pixels = self.source_frames()[0]
        self.assertAlmostEqual(metadata['source_age_seconds'], .625, places=5)
        self.assertEqual(len(pixels), 768 * 576)
        self.assertRaises(ValueError, self.publisher.camera_stream.submit_native_video,
                          image(), self.now)

    def test_decoding_compression_network_never_run_in_typed_admission(self):
        with patch('legacy.xp_acq_control.elyse_agent.camera_stream.zlib.compress',
                   side_effect=AssertionError('Compression ran inline')):
            # Existing VI validation decodes base64 before admission locks.
            # The independent processing worker must never run inline here.
            with patch.object(self.publisher.camera_stream, 'process_once', side_effect=AssertionError('Worker ran inline')):
                self.submit(1)
            self.assertEqual(self.publisher.camera_stream.status()['staging']['accepted'], 1)
        entered, done = threading.Event(), threading.Event()
        failure = []
        def process():
            try:
                entered.set()
                self.publisher.camera_stream.process_once()
            except Exception as error:
                failure.append(error)
            finally:
                done.set()
        with self.publisher.lock:
            with self.runtime._lock:
                worker = threading.Thread(target=process)
                worker.start()
                self.assertTrue(entered.wait(1))
                self.assertTrue(done.wait(1), 'Camera decode waited for publisher/runtime lock')
        worker.join(1)
        self.assertEqual(failure, [])
        self.assertEqual(self.publisher.camera_stream.queue.status()['pending'], 1)

    def test_stage_overflow_is_explicit_and_does_not_reject_vi_or_counter_receipt(self):
        self.publisher.close()
        self.publisher = SupervisionTelemetryPublisher(self.runtime, ('127.0.0.1', 12345),
            KEYS['supervision'], clock=lambda: self.now, camera_stream_configuration=configuration(capacity=1))
        first = self.submit(1, counter=part())
        second = self.submit(2, counter=part())
        self.assertIs(first['independent_camera_staged'], True)
        self.assertIs(second['accepted'], True)
        self.assertIs(second['independent_camera_staged'], False)
        self.assertEqual(self.publisher.typed_accepted, 2)
        self.assertEqual(self.publisher.camera_stream.status()['staging']['rejected_new'], 1)
        self.assertEqual(self.publisher.outbox.peek()['packet']['counter_part']['values'], part()['values'])
        self.drain()
        self.submit(3)
        self.drain()
        self.assertEqual(self.publisher.camera_stream.status()['source_admission']['queue_rejected'], 1)

    def test_half_rate_preserves_source_ids_and_counts_intentional_decimation(self):
        self.publisher.close()
        self.publisher = SupervisionTelemetryPublisher(self.runtime, ('127.0.0.1', 12345),
            KEYS['supervision'], clock=lambda: self.now, camera_stream_configuration=configuration(every_n=2))
        for seq in range(1, 5):
            self.submit(seq)
        self.drain()
        self.assertEqual([meta['sequence'] for meta, raw in self.source_frames()], [1, 3])
        state = self.publisher.camera_stream.status()['source_admission']
        self.assertEqual(state['intentional_decimated'], 2)
        self.assertEqual(state['queue_rejected'], 0)

    def test_two_channel_capture_epochs_do_not_retire_each_other(self):
        for outer, channel, frame_seq in ((1, 2, 1), (2, 3, 1), (3, 2, 2), (4, 3, 2)):
            video = image(frame_seq, capture=('8' if channel == 2 else '9') * 32)
            video['channel'] = channel
            self.submit(outer, video=video)
        self.drain()
        self.assertEqual([(meta['channel'], meta['sequence']) for meta, raw in self.source_frames()],
                         [(2, 1), (3, 1), (2, 2), (3, 2)])

    def test_duplicate_vi_or_image_observation_does_not_enqueue_again(self):
        first = self.submit(1)
        repeated = self.submit(1)
        newer_control_same_image = self.submit(2, video=image(1), counter=part())
        self.assertIs(repeated['duplicate'], True)
        self.assertIsNone(repeated['independent_camera_staged'])
        self.assertIsNone(newer_control_same_image['independent_camera_staged'])
        self.assertEqual(self.publisher.camera_stream.status()['staging']['accepted'], 1)

    def test_default_and_disabled_configs_preserve_sampled_r21_wire_and_three_buttons(self):
        for config in (None, dict(enabled=False)):
            publisher = SupervisionTelemetryPublisher(self.runtime, ('127.0.0.1', 12345),
                KEYS['supervision'], clock=lambda: self.now, camera_stream_configuration=config)
            try:
                publisher.ingest_observation(encoded(observation(video=image())), '127.0.0.1')
                self.assertIsNotNone(publisher.outbox.peek()['packet']['video_frame'])
                self.assertEqual(publisher.status()['raw_video_period_seconds'], 1.)
                self.assertIsNone(publisher.camera_stream)
            finally:
                publisher.close()
        self.assertEqual(BUTTON_LABELS, ('Initialize', 'Deinitialize', 'Stop server'))

    def test_startup_configuration_requires_explicit_vi_mode_and_enabled_owner_telemetry(self):
        original = default_supervision_configuration()
        self.assertNotIn('camera_stream', original)
        self.assertEqual(validate_supervision_configuration(original), original)
        enabled = copy.deepcopy(original)
        enabled['telemetry']['enabled'] = True
        enabled['camera_stream'] = configuration()
        self.assertEqual(validate_supervision_configuration(enabled), enabled)
        for changes in (dict(source_mode='PYTHON_NATIVE'), dict(host='10.20.30.2'), dict(every_n=3),
                        dict(capacity=9999), dict(max_bytes=2**40), dict(port=8767)):
            with self.assertRaises(ValueError):
                validate_camera_stream_configuration(configuration(**changes))
        enabled['telemetry']['enabled'] = False
        with self.assertRaises(ValueError):
            validate_supervision_configuration(enabled)


if __name__ == '__main__':
    unittest.main()
