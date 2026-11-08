"""Tie Python initializer traces to hash-pinned saved diagrams, not captions."""

import json
import struct
import sys
import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

import validate_acq_ni6071e_initializer as ai6071
import validate_acq_ni6220_read_error_contract as ai6220
import validate_acq_ni6602_initializer as counter
import validate_acq_output_initializers as output
from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    SampleClockInputs,
    ScriptedBoundary,
    initialize_dio96,
    initialize_ni6071e,
    initialize_ni6220,
    initialize_ni6602,
    initialize_ni6703,
)
from validate_acq_final_cleanup import constant, tag_array
from validate_acq_modulator_start_event_guards import unique


class ViTranslationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        exports = REPOSITORY / "legacy/xp_acq_agent/data/source_exports"
        path = exports / "ACQ_17_original_members_XML_20261001.zip"
        # Independent validators verify source hashes, argument ports, error
        # nets, task field order, indexing, public locals and call census.
        out_roots = output.checked_roots(path)
        output.validate_dio(out_roots["1_ACQ_INIT_DIO96.vi"])
        output.validate_ao(out_roots["1_ACQ_INIT_NI6703.vi"])
        counter.validate_trees(counter.checked_roots(path))
        ai_roots = ai6220.checked_ni6220_roots(path)["1_ACQ_INIT_NI6220.vi"]
        ai6220.validate_initializer_error(ai_roots)
        ai6220.validate_initializer_configuration(ai_roots)
        ai6071.validate_trees(
            ai6071.checked_roots(exports / "1_ACQ_INIT_NI6071E_XML_shafeb8.zip")
        )
        clock = SampleClockInputs(8123.5, 17)
        cls.results = {}
        for initialize, kwargs in (
            (initialize_dio96, {}),
            (initialize_ni6703, {}),
            (initialize_ni6602, {}),
            (initialize_ni6220, {"clock": clock}),
            (
                initialize_ni6071e,
                {"clock": clock, "trigger_c1": "caller-c1", "trigger_c2": "caller-c2"},
            ),
        ):
            result = initialize(ScriptedBoundary(), error_in=NO_ERROR, **kwargs)
            cls.results[result.source.name] = result
        with ZipFile(path) as archive:
            cls.bd = {
                vi: ET.fromstring(archive.read(vi + "/vi_BDHb.xml"))
                for vi in cls.results
            }
        census = json.loads(
            (
                REPOSITORY / "docs/ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.json"
            ).read_text(encoding="utf-8")
        )
        cls.source_hashes = {
            member["vi"]: member["source_vi_sha256"] for member in census["members"]
        }

    def assert_call_locations(self, result):
        bd = self.bd[result.source.name]
        self.assertEqual(result.source.sha256, self.source_hashes[result.source.name])
        nodes = {
            node.get("uid"): node
            for node in bd.iter()
            if node.get("class") in {"iUse", "polyIUse", "propNode"}
        }
        self.assertEqual({call.key.node_uid for call in result.calls}, set(nodes))
        labels = {
            "create_task": '"DAQmx Create Task.vi"',
            "create_di_channel": '"DAQmx Create Virtual Channel.vi"',
            "create_do_channel": '"DAQmx Create Virtual Channel.vi"',
            "create_ao_voltage_channel": '"DAQmx Create Virtual Channel.vi"',
            "create_ai_voltage_channel": '"DAQmx Create Virtual Channel.vi"',
            "create_co_pulse_ticks_channel": '"DAQmx Create Virtual Channel.vi"',
            "configure_start_trigger": '"DAQmx Trigger.vi"',
            "configure_sample_clock": '"DAQmx Timing.vi"',
            "configure_implicit_timing": '"DAQmx Timing.vi"',
            "start_task": '"DAQmx Start Task.vi"',
            "simple_error_handler": '"Simple Error Handler.vi"',
        }
        for call in result.calls:
            node = nodes[call.key.node_uid]
            diagram = unique(bd, "diag", call.diagram_uid)
            self.assertIn(node, diagram.findall("zPlaneList/*"))
            if call.operation in labels:
                self.assertEqual(
                    node.findtext("label/textRec/text"), labels[call.operation]
                )
            else:
                self.assertEqual(node.get("class"), "propNode")
            if "polymorphic_selector" in call.args:
                self.assertEqual(
                    node.findtext("instanceSelector/menuInstanceUsed"),
                    call.args["polymorphic_selector"],
                )

    def test_every_python_boundary_maps_to_actual_original_node_and_diagram(self):
        for result in self.results.values():
            with self.subTest(vi=result.source.name):
                self.assert_call_locations(result)

    def test_omitting_a_source_call_is_rejected(self):
        result = self.results["1_ACQ_INIT_NI6602.vi"]
        with self.assertRaises(AssertionError):
            self.assert_call_locations(replace(result, calls=result.calls[:-1]))

    def test_wrong_python_diagram_uid_is_rejected(self):
        result = self.results["1_ACQ_INIT_NI6071E.vi"]
        calls = tuple(
            replace(c, diagram_uid="944") if c.key.node_uid == "2959" else c
            for c in result.calls
        )
        with self.assertRaises(AssertionError):
            self.assert_call_locations(replace(result, calls=calls))

    def test_dio_names_port_strings_and_auto_cleanup_match_source_literals(self):
        vi = "1_ACQ_INIT_DIO96.vi"
        frame = self.bd[vi].find("root")
        for i, (name_uid, physical_uid, cleanup_uid) in enumerate(
            (
                ("2526", "2008", "2537"),
                ("1190", "1214", "1204"),
                ("1509", "1533", "1523"),
                ("1854", "1875", "1865"),
                ("2015", "2036", "2026"),
                ("2172", "2193", "2183"),
            )
        ):
            created, channel = self.results[vi].calls[i * 2 : i * 2 + 2]
            output.literal_string(frame, name_uid, created.args["name"])
            output.literal_string(frame, physical_uid, channel.args["physical_channel"])
            self.assertEqual(
                created.args["auto_cleanup"], constant(frame, cleanup_uid) == "01"
            )

    def test_ao_names_channels_ranges_units_and_terminal_configuration_match_source(
        self,
    ):
        vi = "1_ACQ_INIT_NI6703.vi"
        for i, row in enumerate(output.AO_FRAMES):
            frame = unique(self.bd[vi], "diag", row[0])
            body = unique(self.bd[vi], "diag", row[2])
            calls = self.results[vi].calls[i * 11 : (i + 1) * 11]
            output.literal_string(frame, row[5], calls[0].args["name"])
            self.assertEqual(
                [c.args["physical_channel"] for c in calls[1:]],
                tag_array(constant(frame, row[8])),
            )
            max_uid, min_uid, config_uid, units_uid = (
                ("2733", "2571", "1765", "808"),
                ("4713", "4701", "4688", "4675"),
                ("2047", "2035", "2021", "1986"),
                ("1408", "1359", "1208", "1051"),
            )[i]
            for call in calls[1:]:
                self.assertEqual(
                    call.args["maximum"],
                    struct.unpack(">d", bytes.fromhex(constant(body, max_uid)))[0],
                )
                self.assertEqual(
                    call.args["minimum"],
                    struct.unpack(">d", bytes.fromhex(constant(body, min_uid)))[0],
                )
                self.assertEqual(
                    call.args["terminal_configuration_code"],
                    int(constant(body, config_uid), 16),
                )
                self.assertEqual(
                    call.args["units_code"], int(constant(body, units_uid), 16)
                )

    def test_counter_all_connected_tick_trigger_timing_property_arguments_match_source(
        self,
    ):
        vi = "1_ACQ_INIT_NI6602.vi"
        for i, (row, literals) in enumerate(zip(counter.FRAMES, counter.LITERALS)):
            frame = unique(self.bd[vi], "diag", row[0])
            calls = [c for c in self.results[vi].calls if c.diagram_uid == row[0]]
            output.literal_string(frame, literals[0], calls[0].args["name"])
            output.literal_string(frame, literals[2], calls[1].args["physical_channel"])
            output.literal_string(frame, literals[3], calls[1].args["timebase_source"])
            output.literal_string(frame, literals[5], calls[2].args["source"])
            for call_index, argument, literal_index in (
                (1, "high_ticks", 9),
                (1, "low_ticks", 10),
                (1, "idle_state_code", 7),
                (1, "initial_delay", 8),
                (2, "edge_code", 6),
                (4, "idle_state_code", 11),
                (4, "timebase_edge_code", 14),
                (5, "sample_mode_code", 12),
                (5, "samples_per_channel", 13),
            ):
                self.assertEqual(
                    calls[call_index].args[argument],
                    int(constant(frame, literals[literal_index]), 16),
                )
            self.assertEqual(
                calls[0].args["auto_cleanup"], constant(frame, literals[1]) == "01"
            )
            self.assertEqual(
                calls[3].args["retriggerable"], constant(frame, literals[4]) == "01"
            )
            for node_uid, python_codes in (
                (row[4], [calls[3].args["property_code"]]),
                (
                    row[5],
                    [
                        calls[4].args["idle_property_code"],
                        calls[4].args["timebase_edge_property_code"],
                    ],
                ),
            ):
                node = unique(self.bd[vi], "propNode", node_uid)
                self.assertEqual(
                    python_codes,
                    [
                        int(p.findtext("PropItemCode"))
                        for p in node.findall(".//*[@class='propItemInfo']")
                    ],
                )

    def test_ni6220_channel_array_and_ranges_match_source_not_panel_placeholder(self):
        vi = "1_ACQ_INIT_NI6220.vi"
        frame = self.bd[vi].find("root")
        calls = self.results[vi].calls[1:17]
        self.assertEqual(
            [c.args["physical_channel"] for c in calls],
            tag_array(constant(frame, "842")),
        )
        for uid, name in (("1808", "maximum"), ("1770", "minimum")):
            values = struct.unpack(">16d", bytes.fromhex(constant(frame, uid))[4:])
            self.assertEqual(tuple(c.args[name] for c in calls), values)

    def test_ni6071e_both_channel_arrays_ranges_and_volts_units_match_source(self):
        vi = "1_ACQ_INIT_NI6071E.vi"
        for frame_uid, channel_uid, array_uid, min_uid, max_uid, units_uid in (
            ("2383", "2818", "842", "1770", "1808", "3539"),
            ("944", "2959", "982", "1067", "1913", "3384"),
        ):
            frame = unique(self.bd[vi], "diag", frame_uid)
            calls = [c for c in self.results[vi].calls if c.key.node_uid == channel_uid]
            self.assertEqual(
                [c.args["physical_channel"] for c in calls],
                ai6071.tags(frame, array_uid),
            )
            self.assertEqual(
                tuple(c.args["maximum"] for c in calls), ai6071.doubles(frame, max_uid)
            )
            self.assertEqual(
                tuple(c.args["minimum"] for c in calls), ai6071.doubles(frame, min_uid)
            )
            self.assertTrue(
                all(
                    c.args["units_code"] == int(ai6071.literal(frame, units_uid), 16)
                    for c in calls
                )
            )

    def test_ai_clock_trigger_and_read_property_literals_match_originals(self):
        for (
            vi,
            frame_uid,
            timing_uid,
            trigger_uid,
            prop_uid,
            literal_function,
            uids,
        ) in (
            (
                "1_ACQ_INIT_NI6220.vi",
                "3",
                "2393",
                "2454",
                "2561",
                constant,
                ("3732", "3693", "3719", "3706", "3680", "3670"),
            ),
            (
                "1_ACQ_INIT_NI6071E.vi",
                "2383",
                "2393",
                "2454",
                "2561",
                ai6071.literal,
                ("3732", "3693", "3719", "3706", "3680", "3670"),
            ),
            (
                "1_ACQ_INIT_NI6071E.vi",
                "944",
                "998",
                "2212",
                "2380",
                ai6071.literal,
                ("3755", "3651", "3730", "3684", "3621", "3596"),
            ),
        ):
            frame = unique(self.bd[vi], "diag", frame_uid)
            calls = {c.key.node_uid: c for c in self.results[vi].calls}
            payload = bytes.fromhex(literal_function(frame, uids[0]))
            self.assertEqual(
                calls[timing_uid].args["source"], payload[4:].decode("ascii")
            )
            for call_uid, argument, literal_uid in (
                (timing_uid, "sample_mode_code", uids[1]),
                (timing_uid, "edge_code", uids[2]),
                (trigger_uid, "edge_code", uids[3]),
                (prop_uid, "relative_to_code", uids[4]),
            ):
                self.assertEqual(
                    calls[call_uid].args[argument],
                    int(literal_function(frame, literal_uid), 16),
                )
            self.assertEqual(
                calls[prop_uid].args["auto_start"],
                literal_function(frame, uids[5]) == "01",
            )
            node = unique(self.bd[vi], "propNode", prop_uid)
            self.assertEqual(
                [
                    calls[prop_uid].args["relative_to_property_code"],
                    calls[prop_uid].args["auto_start_property_code"],
                ],
                [
                    int(p.findtext("PropItemCode"))
                    for p in node.findall(".//*[@class='propItemInfo']")
                ],
            )


if __name__ == "__main__":
    unittest.main()
