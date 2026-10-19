"""Offline golden traces and injected external returns for five saved VIs."""

import ast
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNASSIGNED,
    UNWIRED,
    CallKey,
    ErrorCluster,
    SampleClockInputs,
    ScriptedBoundary,
    TaskReference,
    init_dio96,
    init_ni6071e,
    init_ni6220,
    init_ni6602,
    init_ni6703,
    initialize_dio96,
    initialize_ni6071e,
    initialize_ni6220,
    initialize_ni6602,
    initialize_ni6703,
)
from DeviceServers.control.elyse_acq.vi_simulation.__main__ import main

FAULT = ErrorCluster(True, -123, "supplied external fault")
WARNING = ErrorCluster(False, 123, "supplied warning")
CLOCK = SampleClockInputs(8123.5, 17)


def all_initializers():
    return (
        (initialize_dio96, {"error_in": NO_ERROR}, 12, 6),
        (initialize_ni6703, {"error_in": NO_ERROR}, 44, 4),
        (initialize_ni6602, {"error_in": NO_ERROR}, 54, 8),
        (initialize_ni6220, {"error_in": NO_ERROR, "clock": CLOCK}, 20, 1),
        (
            initialize_ni6071e,
            {
                "error_in": NO_ERROR,
                "clock": CLOCK,
                "trigger_c1": "/1/PFI3",
                "trigger_c2": "/2/PFI7",
            },
            137,
            2,
        ),
    )


class InitializerGoldenTraceTests(unittest.TestCase):
    def test_all_267_injected_returns_follow_the_distinct_error_contracts(self):
        count = 0
        for initialize, inputs, _, _ in all_initializers():
            baseline = initialize(ScriptedBoundary(), **inputs)
            for target in baseline.calls:
                with self.subTest(vi=baseline.source.name, key=target.key):
                    result = initialize(
                        ScriptedBoundary(errors={target.key: FAULT}), **inputs
                    )
                    if initialize is initialize_ni6703:
                        reaches_final = (
                            target.key.node_uid == "1429" and target.key.iteration == 9
                        )
                    elif initialize in (initialize_ni6220, initialize_ni6071e):
                        last = 15 if initialize is initialize_ni6220 else 63
                        reaches_final = (
                            target.key.iteration in (None, last)
                            and target.operation != "simple_error_handler"
                        )
                    else:
                        reaches_final = True
                    expected = FAULT if reaches_final else NO_ERROR
                    self.assertEqual(result.internal_error, expected)
                    if initialize is initialize_ni6071e:
                        self.assertIs(result.error_out, UNASSIGNED)
                    else:
                        self.assertEqual(result.error_out, expected)
                    count += 1
        self.assertEqual(count, 267)

    def test_all_five_normal_traces_have_267_calls_and_21_task_slots(self):
        calls = slots = 0
        for initialize, inputs, call_count, task_count in all_initializers():
            with self.subTest(vi=initialize.__module__):
                result = initialize(ScriptedBoundary(), **inputs)
                self.assertEqual(len(result.calls), call_count)
                self.assertEqual(len(result.tasks), task_count)
                self.assertEqual(result.internal_error, NO_ERROR)
                self.assertTrue(all(type(t) is TaskReference for t in result.tasks))
                calls += len(result.calls)
                slots += len(result.tasks)
        self.assertEqual((calls, slots), (267, 21))

    def test_dio_task_fields_and_port_literals(self):
        result = initialize_dio96(ScriptedBoundary(), error_in=NO_ERROR)
        self.assertEqual(
            [c.args["name"] for c in result.calls[::2]],
            [
                "C3_IN_DIO",
                "C4_IN_DIO",
                "C5_IN_DIO",
                "C3_OUT_DIO",
                "C4_OUT_DIO",
                "C5_OUT_DIO",
            ],
        )
        self.assertEqual(
            [c.args["physical_channel"] for c in result.calls[1::2]],
            [
                "3/port0:6",
                "4/port0:7",
                "5/port0:6",
                "3/port7:11",
                "4/port8:11",
                "5/port7:11",
            ],
        )
        self.assertEqual(
            result.tasks, tuple(c.returned.task for c in result.calls[1::2])
        )

    def test_dio_public_error_chains_across_all_twelve_calls(self):
        for target in initialize_dio96(ScriptedBoundary(), error_in=NO_ERROR).calls:
            with self.subTest(key=target.key):
                result = initialize_dio96(
                    ScriptedBoundary(errors={target.key: FAULT}), error_in=NO_ERROR
                )
                self.assertEqual(result.error_out, FAULT)
                after = result.calls[
                    result.calls.index(
                        next(c for c in result.calls if c.key == target.key)
                    )
                    + 1 :
                ]
                self.assertTrue(all(c.error_in == FAULT for c in after))

    def test_continuous_chains_preserve_status_false_warning_code_and_source(self):
        for initialize in (initialize_dio96, initialize_ni6602):
            with self.subTest(initializer=initialize.__module__):
                result = initialize(ScriptedBoundary(), error_in=WARNING)
                self.assertEqual(result.error_out, WARNING)
                self.assertTrue(all(c.error_in == WARNING for c in result.calls))

    def test_ao_has_exactly_four_ten_channel_groups_and_no_write_or_start(self):
        result = initialize_ni6703(ScriptedBoundary(), error_in=NO_ERROR)
        for j, device in enumerate(range(6, 10)):
            group = result.calls[j * 11 : (j + 1) * 11]
            self.assertEqual(
                group[0].args, {"name": f"C{device}_NI6703", "auto_cleanup": True}
            )
            self.assertEqual(
                [c.args["physical_channel"] for c in group[1:]],
                [f"{device}/ao{i}" for i in range(10)],
            )
            for channel in group[1:]:
                self.assertEqual(channel.args["minimum"], -10.0)
                self.assertEqual(channel.args["maximum"], 10.0)
                self.assertEqual(
                    channel.args["terminal_configuration_code"], 0xFFFFFFFF
                )
                self.assertIs(channel.error_in, UNWIRED)
                self.assertEqual(channel.task_in, group[0].returned.task)
            self.assertEqual(result.tasks[j], group[-1].returned.task)
        self.assertFalse(
            any(
                c.operation in ("write", "start_task", "stop_task", "clear_task")
                for c in result.calls
            )
        )

    def test_every_ao_create_task_error_is_discarded(self):
        for create in initialize_ni6703(ScriptedBoundary(), error_in=NO_ERROR).calls[
            ::11
        ]:
            with self.subTest(key=create.key):
                result = initialize_ni6703(
                    ScriptedBoundary(errors={create.key: FAULT}), error_in=NO_ERROR
                )
                self.assertEqual(result.error_out, NO_ERROR)
                self.assertTrue(
                    all(
                        c.error_in is UNWIRED
                        for c in result.calls
                        if c.key.iteration is not None
                    )
                )

    def test_ao_early_channel_errors_are_not_accumulated(self):
        for module_frame in init_ni6703.FRAMES:
            key = CallKey(init_ni6703.SOURCE.name, module_frame[4], 0)
            with self.subTest(key=key):
                result = initialize_ni6703(
                    ScriptedBoundary(errors={key: FAULT}), error_in=NO_ERROR
                )
                self.assertEqual(result.error_out, NO_ERROR)

    def test_ao_previous_last_channel_error_only_seeds_next_create_task(self):
        for frame in range(3):
            key = CallKey(init_ni6703.SOURCE.name, init_ni6703.FRAMES[frame][4], 9)
            result = initialize_ni6703(
                ScriptedBoundary(errors={key: FAULT}), error_in=NO_ERROR
            )
            self.assertEqual(result.calls[(frame + 1) * 11].error_in, FAULT)
            self.assertIs(result.calls[(frame + 1) * 11 + 1].error_in, UNWIRED)
            self.assertEqual(result.error_out, NO_ERROR)

    def test_ao_final_channel_error_is_public_error_out(self):
        key = CallKey(init_ni6703.SOURCE.name, "1429", 9)
        result = initialize_ni6703(
            ScriptedBoundary(errors={key: WARNING}), error_in=FAULT
        )
        self.assertEqual(result.error_out, WARNING)

    def test_ao_ordinary_task_tunnel_does_not_feed_channel_return_into_next_iteration(
        self,
    ):
        keys = [CallKey(init_ni6703.SOURCE.name, "847", i) for i in (0, 9)]
        refs = [TaskReference("first-override"), TaskReference("last-override")]
        result = initialize_ni6703(
            ScriptedBoundary(tasks=dict(zip(keys, refs))), error_in=NO_ERROR
        )
        self.assertNotEqual(result.calls[2].task_in, refs[0])
        self.assertEqual(result.calls[10].task_in, result.calls[0].returned.task)
        self.assertEqual(result.tasks[0], refs[1])

    def test_counter_ticks_trigger_edges_properties_and_six_starts(self):
        result = initialize_ni6602(ScriptedBoundary(), error_in=NO_ERROR)
        for i, frame in enumerate(init_ni6602.FRAMES):
            group = [c for c in result.calls if c.diagram_uid == frame[0]]
            self.assertEqual(
                [c.key.node_uid for c in group],
                [uid for uid in frame[1:] if uid is not None],
            )
            self.assertEqual(group[1].args["physical_channel"], f"10/ctr{i}")
            self.assertEqual(group[1].args["timebase_source"], "/10/PFI11")
            self.assertEqual(
                group[1].args["high_ticks"],
                (20, 3620000, 200, 60, 60, 2000, 56, 100000)[i],
            )
            self.assertEqual(
                group[1].args["low_ticks"],
                (31, 200, 43558, 43658, 43500, 101600, 43500, 20)[i],
            )
            self.assertEqual(
                group[2].args["source"], f"/10/PFI{(34, 34, 30, 34, 30, 30, 30, 10)[i]}"
            )
            self.assertEqual(group[2].args["edge_code"], 0x27BB if i == 7 else 0x2828)
            self.assertTrue(group[3].args["retriggerable"])
            self.assertEqual(group[4].args["timebase_edge_code"], 0x2828)
            self.assertEqual(group[5].args["samples_per_channel"], 1)
        self.assertEqual(sum(c.operation.startswith("set_") for c in result.calls), 16)
        self.assertEqual(
            [c.diagram_uid for c in result.calls if c.operation == "start_task"],
            ["9978", "8666", "6900", "6943", "9487", "7856"],
        )

    def test_every_counter_error_reaches_public_output_and_later_frames(self):
        for target in initialize_ni6602(ScriptedBoundary(), error_in=NO_ERROR).calls:
            with self.subTest(key=target.key):
                result = initialize_ni6602(
                    ScriptedBoundary(errors={target.key: FAULT}), error_in=NO_ERROR
                )
                self.assertEqual(result.error_out, FAULT)
                index = next(
                    i for i, c in enumerate(result.calls) if c.key == target.key
                )
                self.assertTrue(
                    all(c.error_in == FAULT for c in result.calls[index + 1 :])
                )

    def test_counter_supplied_task_return_is_forwarded_not_reconstructed_from_name(
        self,
    ):
        key = CallKey(init_ni6602.SOURCE.name, "10044")
        ref = TaskReference("external-return-fixture")
        result = initialize_ni6602(
            ScriptedBoundary(tasks={key: ref}), error_in=NO_ERROR
        )
        self.assertEqual(result.calls[2].task_in, ref)
        self.assertEqual(result.tasks[0], ref)

    def test_ai_ranges_and_clock_inputs_are_not_guessed_defaults(self):
        for initialize, inputs, _, _ in all_initializers()[-2:]:
            result = initialize(ScriptedBoundary(), **inputs)
            for timing in (
                c for c in result.calls if c.operation == "configure_sample_clock"
            ):
                self.assertEqual(timing.args["rate_hz"], 8123.5)
                self.assertEqual(timing.args["samples_per_channel"], 17)
                self.assertEqual(timing.args["source"], "OnboardClock")
            self.assertFalse(any(c.operation == "start_task" for c in result.calls))
        ni6220 = initialize_ni6220(ScriptedBoundary(), clock=CLOCK, error_in=FAULT)
        channels = ni6220.calls[1:17]
        self.assertEqual(
            [c.args["maximum"] for c in channels],
            [10.0 if i in (4, 5, 6, 7) else 0.2 for i in range(16)],
        )
        ni6071 = initialize_ni6071e(
            ScriptedBoundary(),
            clock=CLOCK,
            error_in=FAULT,
            trigger_c1="/1/PFI3",
            trigger_c2="/2/PFI7",
        )
        self.assertEqual(
            [c.args["maximum"] for c in ni6071.calls[1:65]],
            [0.05 if i == 2 else 1.0 if i in (3, 4) else 10.0 for i in range(64)],
        )
        self.assertEqual([c.args["maximum"] for c in ni6071.calls[69:133]], [10.0] * 64)
        self.assertEqual(
            [
                c.args["source"]
                for c in ni6071.calls
                if c.operation == "configure_start_trigger"
            ],
            ["/1/PFI3", "/2/PFI7"],
        )

    def test_ni6220_public_error_in_is_ignored_and_final_error_is_returned(self):
        result = initialize_ni6220(ScriptedBoundary(), clock=CLOCK, error_in=FAULT)
        self.assertIs(result.calls[0].error_in, UNWIRED)
        self.assertEqual(result.error_out, NO_ERROR)
        key = CallKey(init_ni6220.SOURCE.name, "2561")
        result = initialize_ni6220(
            ScriptedBoundary(errors={key: WARNING}), clock=CLOCK, error_in=FAULT
        )
        self.assertEqual(result.error_out, WARNING)

    def test_ai_channel_errors_use_shared_create_error_not_previous_channel_error(self):
        for initialize, inputs, _, _ in all_initializers()[-2:]:
            source = (
                init_ni6220.SOURCE
                if initialize is initialize_ni6220
                else init_ni6071e.SOURCE
            )
            result = initialize(
                ScriptedBoundary(errors={CallKey(source.name, "2818", 0): FAULT}),
                **inputs,
            )
            channels = [c for c in result.calls if c.key.node_uid == "2818"]
            self.assertTrue(all(c.error_in == NO_ERROR for c in channels))
            self.assertEqual(result.internal_error, NO_ERROR)

    def test_ai_last_channel_task_return_feeds_timing_but_not_loop_input(self):
        for initialize, inputs, _, _ in all_initializers()[-2:]:
            count = 16 if initialize is initialize_ni6220 else 64
            source = (
                init_ni6220.SOURCE
                if initialize is initialize_ni6220
                else init_ni6071e.SOURCE
            )
            ref = TaskReference("last-channel-task")
            first = TaskReference("first-channel-task")
            result = initialize(
                ScriptedBoundary(
                    tasks={
                        CallKey(source.name, "2818", 0): first,
                        CallKey(source.name, "2818", count - 1): ref,
                    }
                ),
                **inputs,
            )
            self.assertNotEqual(result.calls[2].task_in, first)
            timing = next(c for c in result.calls if c.key.node_uid == "2393")
            self.assertEqual(timing.task_in, ref)
            self.assertEqual(result.tasks[0], ref)

    def test_ai_last_channel_error_feeds_timing(self):
        result = initialize_ni6220(
            ScriptedBoundary(
                errors={CallKey(init_ni6220.SOURCE.name, "2818", 15): FAULT}
            ),
            clock=CLOCK,
            error_in=NO_ERROR,
        )
        self.assertEqual(result.calls[17].error_in, FAULT)
        self.assertEqual(result.error_out, FAULT)

    def test_ni6071e_public_error_out_stays_unassigned_or_preserves_explicit_seed(self):
        kwargs = dict(
            clock=CLOCK, trigger_c1="/1/PFI0", trigger_c2="/2/PFI0", error_in=FAULT
        )
        result = initialize_ni6071e(ScriptedBoundary(), **kwargs)
        self.assertIs(result.calls[0].error_in, UNWIRED)
        self.assertIs(result.error_out, UNASSIGNED)
        result = initialize_ni6071e(
            ScriptedBoundary(), public_error_out_seed=WARNING, **kwargs
        )
        self.assertEqual(result.error_out, WARNING)

    def test_ni6071e_c1_error_seeds_c2_and_handler_output_does_not_become_public_error(
        self,
    ):
        source = init_ni6071e.SOURCE.name
        result = initialize_ni6071e(
            ScriptedBoundary(
                errors={CallKey(source, "2561"): FAULT, CallKey(source, "134"): WARNING}
            ),
            clock=CLOCK,
            trigger_c1="a",
            trigger_c2="b",
            error_in=NO_ERROR,
        )
        self.assertEqual(result.calls[68].error_in, FAULT)
        self.assertEqual(result.calls[-1].error_in, FAULT)
        self.assertEqual(result.calls[-1].returned.error, WARNING)
        self.assertEqual(result.internal_error, FAULT)
        self.assertIs(result.error_out, UNASSIGNED)


class SimulationBoundaryTests(unittest.TestCase):
    def test_ai_wrong_clock_type_fails_before_any_boundary_call(self):
        for initialize, inputs, _, _ in all_initializers()[-2:]:
            boundary = ScriptedBoundary()
            with self.assertRaisesRegex(TypeError, "explicit SampleClockInputs"):
                initialize(boundary, **dict(inputs, clock=object()))
            self.assertEqual(boundary.calls, ())

    def test_all_helper_results_are_json_serializable_without_driver_state(self):
        for initialize, inputs, _, _ in all_initializers():
            report = json.loads(
                json.dumps(
                    initialize(ScriptedBoundary(), **inputs).to_dict(), allow_nan=False
                )
            )
            self.assertEqual(report["mode"], "simulation-only")
            self.assertNotIn("hardware_ready", report)
            self.assertNotIn("started_tasks", report)

    def test_fixture_data_is_copied_and_unknown_keys_are_rejected_on_completion(self):
        key = CallKey(init_dio96.SOURCE.name, "2471")
        mapping = {key: FAULT}
        boundary = ScriptedBoundary(errors=mapping)
        mapping[key] = NO_ERROR
        result = initialize_dio96(boundary, error_in=NO_ERROR)
        self.assertEqual(result.error_out, FAULT)
        boundary.assert_all_fixtures_used()
        unused = ScriptedBoundary(errors={CallKey("unknown.vi", "999"): FAULT})
        initialize_dio96(unused, error_in=NO_ERROR)
        with self.assertRaisesRegex(ValueError, "unused simulation fixtures"):
            unused.assert_all_fixtures_used()

    def test_duplicate_call_rejected_in_one_fixture_trace(self):
        boundary = ScriptedBoundary()
        initialize_dio96(boundary, error_in=NO_ERROR)
        with self.assertRaisesRegex(ValueError, "duplicate simulation call"):
            initialize_dio96(boundary, error_in=NO_ERROR)

    def test_live_adapter_or_callback_is_not_supported(self):
        for initialize, inputs, _, _ in all_initializers():
            with self.subTest(initializer=initialize.__module__):
                with self.assertRaisesRegex(TypeError, "in-memory ScriptedBoundary"):
                    initialize(object(), **inputs)
        with self.assertRaisesRegex(TypeError, "error fixtures"):
            ScriptedBoundary(errors={CallKey("a", "1"): lambda: FAULT})

    def test_package_imports_are_only_local_modules_and_small_standard_library(self):
        package = Path(init_dio96.__file__).parent
        allowed = {
            "__future__",
            "dataclasses",
            "enum",
            "math",
            "typing",
            "argparse",
            "json",
        }
        shared = {
            "stop_lifecycle.py": ("saved_stop", {"saved_stop"}),
            "supervision_reads.py": ("saved_sup_reads", {
                "ReaderReturn", "read_chain", "independent_read",
                "replay_saved_sup_reads",
            }),
            "event_envelope.py": ("saved_requests", {"procedure_entry_values"}),
            "timeout_dispatch.py": ("saved_dispatch", {"dispatch_values"}),
            "timeout_reads.py": ("saved_psp_reads", {"route_read_values", "replay_saved_psp_reads"}),
            "final_cleanup.py": ("saved_cleanup", {
                "VARIABLES", "FIXED_PSP_TAGS", "TPG_BRANCHES", "PSP_HANDLER",
                "CleanupEvent", "begin_cleanup", "cleanup_ready", "plan_cleanup_step",
                "commit_cleanup_step", "replay_saved_cleanup",
            }),
            "initialization_caller.py": ("saved_initializer", {
                "AI_ARGUMENTS", "STAGES", "route_ai_test_values",
                "route_initializer_values", "replay_saved_initializer",
            }),
            "saved_xnode.py": ("saved_xnode", {
                "ErrorValue", "XNodeResult", "evaluate_saved_xnode", "replay_saved_xnode",
            }),
            "saved_timing.py": ("saved_timing", {
                "TIMING_FIELDS", "Timing", "evaluate_saved_timing", "replay_saved_timing",
                "timing_from_json", "timing_to_json",
            }),
        }
        extra_shared = {
            # Exact exported facade only. The shared-core AST checks below
            # still forbid network, drivers and non-stdlib dependencies.
            "acquisition_vi_15_static_interpreted.py": {
                "saved_acq_app15_static_interpreted": {
                    "project_app15_static_interpreted",
                },
            },
            "acquisition_vi_16.py": {
                "saved_acq_app16": {"compute_vi", "compute_saved_app16"},
            },
            "supervision_vi_22.py": {
                "saved_sup_app22": {"project_app22_source"},
            },
            "supervision_vi_30.py": {
                "saved_sup_app30": {"convert_property_node_font_to_graphics_font"},
            },
            "acquisition_event_45123.py": {
                "saved_acq_event_45123": {"replay_event", "replay_saved_acq_event_45123"},
            },
            "supervision_event_65050.py": {
                "saved_sup_event_65050": {"project_event_65050", "replay_saved_sup_event_65050"},
            },
            "acquisition_event_34191.py": {
                "saved_acq_event_34191": {"replay_event", "replay_saved_acq_event_34191"},
            },
            "supervision_event_38030.py": {
                "saved_sup_event_38030": {"project_event_38030", "replay_saved_sup_event_38030"},
            },
            "acquisition_event_43634.py": {
                "saved_acq_event_43634": {"replay_event", "replay_saved_acq_event_43634"},
            },
            "supervision_event_53716.py": {
                "saved_sup_event_53716": {"project_event_53716", "replay_saved_sup_event_53716"},
            },
            "acquisition_event_31552.py": {
                "saved_acq_event_31552": {"replay_event", "replay_saved_acq_event_31552"},
            },
            "supervision_event_18780.py": {
                "saved_sup_event_18780": {"project_event_18780", "replay_saved_sup_event_18780"},
            },
            "acquisition_event_48846.py": {
                "saved_acq_event_48846": {"replay_event", "replay_saved_acq_event_48846"},
            },
            "supervision_event_33463.py": {
                "saved_sup_event_33463": {"project_event_33463", "replay_saved_sup_event_33463"},
            },
            "acquisition_event_8896.py": {
                "saved_acq_event_8896": {"replay_event", "replay_saved_acq_event_8896"},
            },
            "supervision_event_38707.py": {
                "saved_sup_event_38707": {"project_event_38707", "replay_saved_sup_event_38707"},
            },
            "acquisition_event_23113.py": {
                "saved_acq_event_23113": {"replay_event", "replay_saved_acq_event_23113"},
            },
            "supervision_event_5847.py": {
                "saved_sup_event_5847": {"project_event_5847", "replay_saved_sup_event_5847"},
            },
            "acquisition_event_38732.py": {
                "saved_acq_event_38732": {"replay_event", "replay_saved_acq_event_38732"},
            },
            "supervision_event_26490.py": {
                "saved_sup_event_26490": {"project_event_26490", "replay_saved_sup_event_26490"},
            },
            "acquisition_event_37991.py": {
                "saved_acq_event_37991": {"replay_event", "replay_saved_acq_event_37991"},
            },
            "supervision_event_23880.py": {
                "saved_sup_event_23880": {"project_event_23880", "replay_saved_sup_event_23880"},
            },
            "acquisition_event_17899.py": {
                "saved_acq_event_17899": {"replay_event", "replay_saved_acq_event_17899"},
            },
            "supervision_event_53772.py": {
                "saved_sup_event_53772": {"project_event_53772", "replay_saved_sup_event_53772"},
            },
            "acquisition_event_23143.py": {
                "saved_acq_event_23143": {"replay_event", "replay_saved_acq_event_23143"},
            },
            "supervision_event_23770.py": {
                "saved_sup_event_23770": {"project_event_23770", "replay_saved_sup_event_23770"},
            },
            "acquisition_event_35942.py": {
                "saved_acq_event_35942": {"replay_event", "replay_saved_acq_event_35942"},
            },
            "supervision_event_56943.py": {
                "saved_sup_event_56943": {"project_event_56943", "replay_saved_sup_event_56943"},
            },
            "acquisition_event_40079.py": {
                "saved_acq_event_40079": {"replay_event", "replay_saved_acq_event_40079"},
            },
            "supervision_event_53656.py": {
                "saved_sup_event_53656": {"project_event_53656", "replay_saved_sup_event_53656"},
            },
            "acquisition_event_42457.py": {
                "saved_acq_event_42457": {"replay_event", "replay_saved_acq_event_42457"},
            },
            "supervision_event_47072.py": {
                "saved_sup_event_47072": {"project_event_47072", "replay_saved_sup_event_47072"},
            },
            "acquisition_event_34531.py": {
                "saved_acq_event_34531": {"replay_event", "replay_saved_acq_event_34531"},
            },
            "supervision_event_30817.py": {
                "saved_sup_event_30817": {"project_event_30817", "replay_saved_sup_event_30817"},
            },
            "acquisition_event_23449.py": {
                "saved_acq_event_23449": {"replay_event", "replay_saved_acq_event_23449"},
            },
            "supervision_position_t3_event.py": {
                "saved_sup_position_t3": {"project_position_t3", "replay_saved_sup_position_t3"},
            },
            "acquisition_event_26012.py": {
                "saved_acq_event_26012": {"replay_event", "replay_saved_acq_event_26012"},
            },
            "supervision_position_t2_event.py": {
                "saved_sup_position_t2": {"project_position_t2", "replay_saved_sup_position_t2"},
            },
            "acquisition_event_22879.py": {
                "saved_acq_event_22879": {"replay_event", "replay_saved_acq_event_22879"},
            },
            "supervision_gain_event.py": {
                "saved_sup_gain": {"project_gain", "replay_saved_sup_gain"},
            },
            "acquisition_control_event.py": {
                "saved_acq_event_33620": {"replay_event", "replay_saved_acq_event_33620"},
            },
            "supervision_frequency_event.py": {
                "saved_sup_frequency": {"project_frequency", "replay_saved_sup_frequency"},
            },
            "saved_card_initializers.py": {
                "saved_card_init": {"project_dio96", "project_ni6071e", "project_ni6259"},
                "saved_card_replay": {"replay_saved_card_init"},
            },
            "saved_supervision_helpers.py": {
                "saved_sup_helpers": {"DomainRefusal", "discrepancy_vdeviee", "discrepancy_vdirecte", "profile_xy"},
                "saved_sup_replay": {"replay_saved_sup_helpers"},
            },
        }
        # Qualified shared cores are repository-owned stdlib bodies. Check
        # their dependencies too, rather than admitting an external package.
        core_modules = {module for module, _ in shared.values()}
        core_modules.update(module for modules in extra_shared.values() for module in modules)
        for module in sorted(core_modules):
            core = package.parents[3] / "legacy/xp_acq_agent/elyse_agent" / (module + ".py")
            for node in ast.walk(ast.parse(core.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    allowed_core_imports = {"json"} if module == "saved_sup_event_30817" else ({"json", "math"} if module == "saved_sup_event_47072" else ({"json"} if module in ("saved_sup_event_26490", "saved_sup_event_23880", "saved_sup_event_53772", "saved_sup_event_23770", "saved_sup_event_56943", "saved_sup_event_53656") else ({"math", "struct"} if module in ("saved_sup_event_65050", "saved_sup_event_38030", "saved_sup_event_53716", "saved_sup_event_18780", "saved_sup_event_33463", "saved_sup_event_38707", "saved_sup_event_5847") else {"math"})))
                    self.assertTrue(all(alias.name in allowed_core_imports for alias in node.names), core)
                if isinstance(node, ast.ImportFrom):
                    if node.level:
                        if module in ("saved_card_replay", "saved_sup_replay"):
                            dependency = {"saved_card_replay": "saved_card_init", "saved_sup_replay": "saved_sup_helpers"}[module]
                            self.assertEqual((node.level, node.module), (1, None), core)
                            self.assertEqual([(alias.name, alias.asname) for alias in node.names], [(dependency, "core")], core)
                        elif module == "saved_cleanup":
                            self.assertEqual((node.level, node.module), (1, "saved_initializer"), core)
                            self.assertEqual({alias.name for alias in node.names},
                                {"OpaqueReference", "UNWIRED", "require_error", "json_error", "exact", "encode_error"}, core)
                        else:
                            self.assertEqual((node.level, node.module), (1, "saved_xnode"), core)
                            self.assertEqual({alias.name for alias in node.names}, {"ErrorValue"}, core)
                    elif node.module == "collections":
                        self.assertEqual({alias.name for alias in node.names}, {"namedtuple"}, core)
                    else:
                        self.assertEqual(node.module, "__future__", core)
        for path in package.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(n.name in allowed for n in node.names), path)
                if isinstance(node, ast.ImportFrom) and not node.level:
                    if path.name == "stop_lifecycle.py" and node.module == "legacy.xp_acq_agent.elyse_agent":
                        self.assertEqual([(a.name, a.asname) for a in node.names], [("saved_stop", "_shared")], path)
                        continue
                    if path.name in shared:
                        module, names = shared[path.name]
                        if node.module == "legacy.xp_acq_agent.elyse_agent." + module:
                            self.assertEqual({alias.name for alias in node.names}, names, path)
                            continue
                    if path.name in extra_shared:
                        modules = extra_shared[path.name]
                        prefix = "legacy.xp_acq_agent.elyse_agent."
                        if node.module.startswith(prefix) and node.module[len(prefix):] in modules:
                            self.assertEqual({alias.name for alias in node.names}, modules[node.module[len(prefix):]], path)
                            continue
                    if node.module == "types":
                        # Only the immutable in-memory mapping wrapper is allowed.
                        self.assertEqual(
                            {alias.name for alias in node.names},
                            {"MappingProxyType"},
                            path,
                        )
                        continue
                    self.assertIn(node.module, allowed, path)

    def test_python_only_input_guards_are_explicit(self):
        for rate, count in (
            (True, 1),
            (float("nan"), 1),
            (float("inf"), 1),
            (1.0, True),
            (1.0, -1),
            (1.0, 2.1),
        ):
            with self.subTest(rate=rate, count=count), self.assertRaises(ValueError):
                SampleClockInputs(rate, count)
        self.assertEqual(SampleClockInputs(-1.0, 0).rate_hz, -1.0)
        with self.assertRaises(TypeError):
            ErrorCluster(False, True)

    def test_trace_json_preserves_unknowns_and_faults_without_claiming_task_success(
        self,
    ):
        result = initialize_ni6071e(
            ScriptedBoundary(),
            clock=CLOCK,
            trigger_c1="a",
            trigger_c2="b",
            error_in=FAULT,
        )
        report = json.loads(json.dumps(result.to_dict(), allow_nan=False))
        self.assertEqual(report["mode"], "simulation-only")
        self.assertEqual(report["error_out"], {"connection": "unassigned"})
        self.assertEqual(report["calls"][0]["error_in"], {"connection": "unwired"})
        self.assertNotIn("hardware_ready", report)

    def test_cli_prints_one_trace_not_acquisition_lifecycle(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(["ni6220", "--rate-hz", "8123.5", "--samples", "17"]), 0
            )
        report = json.loads(output.getvalue())
        self.assertEqual(report["source_vi"], "1_ACQ_INIT_NI6220.vi")
        self.assertEqual(len(report["calls"]), 20)

    def test_cli_rejects_guessed_ai_inputs_and_unused_options(self):
        for args in (
            ["ni6220"],
            ["ni6071e", "--rate-hz", "1", "--samples", "1"],
            ["dio96", "--rate-hz", "1"],
            ["ni6602", "--trigger-c1", "a"],
        ):
            with (
                self.subTest(args=args),
                redirect_stderr(StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                main(args)
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
