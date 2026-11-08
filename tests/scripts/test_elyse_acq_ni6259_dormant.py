"""Original six-diagram proof must fail for changed wiring or semantics."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from DeviceServers.control.elyse_acq.vi_simulation import ni6259_dormant as model
from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    SampleClockInputs,
    ScriptedBoundary,
)
from validate_acq_modulator_start_event_guards import unique
from validate_acq_ni6259_dormant import (
    INIT,
    INIT_WIRES,
    READ,
    READ_WIRES,
    checked_roots,
    coefficients,
    validate_initializer,
    validate_reader,
)


class NI6259SourceProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = checked_roots()

    def test_all_six_original_diagrams_and49_direct_nets(self):
        init = validate_initializer(self.roots[INIT])
        reader = validate_reader(self.roots[READ])
        self.assertEqual(init["diagrams"] + reader["diagrams"], 6)
        self.assertEqual(init["direct_nets"] + reader["direct_nets"], 49)
        self.assertFalse(init["public_error_out_written"])
        self.assertFalse(reader["saved_calibration"])

    def test_each_of49_direct_nets_is_independently_required(self):
        for name, specs, validator in (
            (INIT, INIT_WIRES, validate_initializer),
            (READ, READ_WIRES, validate_reader),
        ):
            for uid, wires in specs.items():
                for wire in wires:
                    with self.subTest(vi=name, diagram=uid, wire=wire):
                        roots = deepcopy(self.roots[name])
                        frame = unique(roots["vi_BDHb.xml"], "diag", uid)
                        frame.find(f"signalList/*/termList/*[@uid='{wire[0]}']").set(
                            "uid", "999999999"
                        )
                        with self.assertRaisesRegex(AssertionError, "wire set"):
                            validator(roots)

    def test_connected_initializer_literals_cannot_be_substituted(self):
        for uid in (
            "842",
            "3638",
            "3659",
            "3670",
            "3680",
            "3693",
            "3719",
            "3732",
            "3313",
            "3382",
            "616",
        ):
            with self.subTest(port=uid):
                roots = deepcopy(self.roots[INIT])
                term = unique(roots["vi_BDHb.xml"], "term", uid)
                value = term.find("dco/ConstValue")
                value.text = value.text[:-1] + ("0" if value.text[-1] != "0" else "1")
                with self.assertRaises(AssertionError):
                    validate_initializer(roots)

    def test_leftover_disconnected_ranges_and_timebase_are_not_applied(self):
        roots = deepcopy(self.roots[INIT])
        for uid in ("1770", "1808", "3094", "3706"):
            unique(roots["vi_BDHb.xml"], "term", uid).find("dco/ConstValue").text = "00"
        self.assertEqual(validate_initializer(roots)["channels"], 8)

    def test_trigger_instance_and_concrete_link_are_independent_requirements(self):
        roots = deepcopy(self.roots[INIT])
        unique(roots["vi_BDHb.xml"], "polyIUse", "2454").find(
            "instanceSelector/menuInstanceUsed"
        ).text = "03"
        with self.assertRaisesRegex(AssertionError, "call selection"):
            validate_initializer(roots)
        roots = deepcopy(self.roots[INIT])
        for item in roots["vi.xml"].findall(".//IUVI/LinkSaveQualName/String"):
            if item.text == "DAQmx Start Trigger (None).vi":
                item.text = "DAQmx Start Trigger (Digital Edge).vi"
        with self.assertRaisesRegex(AssertionError, "concrete callees"):
            validate_initializer(roots)

    def test_each_initializer_tunnel_indexing_and_direction_is_required(self):
        for uid in ("2686", "2690", "2694", "2700", "2737", "1351"):
            roots = deepcopy(self.roots[INIT])
            unique(roots["vi_BDHb.xml"], "forLoop", "2680").find(
                f"termList/*[@uid='{uid}']/dco/objFlags"
            ).text = "0"
            with (
                self.subTest(uid=uid),
                self.assertRaisesRegex(AssertionError, "tunnel"),
            ):
                validate_initializer(roots)

    def test_read_literal_bound_timeout_and_false_are_required(self):
        for uid in ("670", "57", "1160"):
            roots = deepcopy(self.roots[READ])
            unique(roots["vi_BDHb.xml"], "term", uid).find("dco/ConstValue").text = "01"
            with (
                self.subTest(uid=uid),
                self.assertRaisesRegex(AssertionError, "literal"),
            ):
                validate_reader(roots)

    def test_each_reader_tunnel_polarity_is_required(self):
        for klass, owner, uid in (
            ("forLoop", "612", "276"),
            ("forLoop", "612", "1152"),
            ("select", "861", "1001"),
            ("select", "861", "1016"),
        ):
            roots = deepcopy(self.roots[READ])
            unique(roots["vi_BDHb.xml"], klass, owner).find(
                f"termList/*[@uid='{uid}']/dco/objFlags"
            ).text = "0"
            with (
                self.subTest(uid=uid),
                self.assertRaisesRegex(AssertionError, "tunnel"),
            ):
                validate_reader(roots)

    def test_coefficients_and_typed_mean_output_not_silently_changed(self):
        for uid in ("756", "804"):
            roots = deepcopy(self.roots[READ])
            term = unique(roots["vi_BDHb.xml"], "term", uid).find("dco/ConstValue")
            term.text = term.text[:-1] + "1"
            with (
                self.subTest(uid=uid),
                self.assertRaisesRegex(AssertionError, "coefficient"),
            ):
                validate_reader(roots)
        roots = deepcopy(self.roots[READ])
        unique(roots["vi_BDHb.xml"], "polyIUse", "359").find(
            "termList/*[@uid='554']/dco/typeDesc"
        ).text = "TypeID(53)"
        with self.assertRaisesRegex(AssertionError, "port type"):
            validate_reader(roots)

    def test_source_values_agree_with_model_not_copied_from_filename(self):
        import struct

        from validate_acq_final_cleanup import constant, tag_array

        init = self.roots[INIT]["vi_BDHb.xml"]
        result = model.initialize(
            ScriptedBoundary(), clock=SampleClockInputs(1.0, 0), error_in=NO_ERROR
        )
        self.assertEqual(result.source.sha256, model.INIT_SOURCE.sha256)
        frame, body = unique(init, "diag", "3"), unique(init, "diag", "2798")
        self.assertEqual(
            [c.args["physical_channel"] for c in result.calls[1:9]],
            tag_array(constant(frame, "842")),
        )
        for call in result.calls[1:9]:
            self.assertEqual(
                call.args["minimum"],
                struct.unpack(">d", bytes.fromhex(constant(body, "3382")))[0],
            )
            self.assertEqual(
                call.args["maximum"],
                struct.unpack(">d", bytes.fromhex(constant(body, "3313")))[0],
            )
            self.assertEqual(
                call.args["terminal_configuration_code"], int(constant(body, "616"), 16)
            )
        slopes, offsets = coefficients(self.roots[READ])
        self.assertEqual(slopes, tuple(float(v) for v in model.C1_SLOPES))
        self.assertEqual(offsets, model.C1_OFFSETS)


if __name__ == "__main__":
    unittest.main()
