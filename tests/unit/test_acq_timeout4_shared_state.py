"""Mutation tests for saved native frame-4 hook; never execute a VI."""

import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from validate_acq_timeout4_shared_state import (  # noqa: E402
    AFTER,
    BEFORE,
    COLLECTOR,
    NEW_FRAME,
    Export,
    Types,
    node,
    validate,
    validate_hook,
    validate_preservation,
)

EVIDENCE = Path("C:/dev/ELYSE-ACQ-telemetry/2026-10-13")
NATIVE = EVIDENCE / "shared_state_native_helpers/export" / COLLECTOR


@unittest.skipUnless(
    (EVIDENCE / AFTER / "export/0_ACQ_ELYSE/vi.xml").is_file()
    and (NATIVE / "vi.xml").is_file(),
    "requires local native hook evidence",
)
class Timeout4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = (
            Export(EVIDENCE / BEFORE / "export/0_ACQ_ELYSE"),
            Export(EVIDENCE / AFTER / "export/0_ACQ_ELYSE"),
            Export(NATIVE),
        )

    def setUp(self):
        self.before, after, self.collector = self.evidence
        self.after = deepcopy(after)

    def test_native_hook_and_pressure_pass_without_delivery_claim(self):
        report = validate(self.before, self.after, self.collector)
        self.assertTrue(report["main_timeout_integrated"])
        self.assertEqual(report["preserved_diagrams"], 475)
        self.assertEqual(report["pressure"]["zero_based_fields"], [10, 11, 20])
        for flag in (
            "telemetry_complete",
            "native_vi_executed",
            "new_transport_delivered",
            "queue_owner_connected",
            "consumer_connected",
            "run_on_open",
        ):
            self.assertFalse(report[flag])

    def hook_fails(self, message):
        with self.assertRaisesRegex(AssertionError, message):
            validate_hook(self.before, self.after)

    def test_frame_inserted_before_cooling_rejected(self):
        frames = node(self.after.bd, "sequence", "10111").find("diagramList")
        last = frames[-1]
        frames.remove(last)
        frames.insert(3, last)
        self.hook_fails("follow all four")

    def test_cut_source_reference_rejected(self):
        signals = node(self.after.bd, "diag", NEW_FRAME).find("signalList")
        signals.remove(signals[-1])
        self.hook_fails("wiring changed")

    def test_error_output_left_unwired_rejected(self):
        signals = node(self.after.bd, "diag", NEW_FRAME).find("signalList")
        signals.remove(signals[0])
        self.hook_fails("wiring changed")

    def test_diagnostic_command_instead_of_indicator_rejected(self):
        node(self.after.fp, "fPDCO", "67359").find("objFlags").text = "0"
        self.hook_fails("non-connector indicator")

    def test_diagnostic_exported_as_connector_rejected(self):
        node(self.after.fp, "fPDCO", "67359").find("conNum").text = "3"
        self.hook_fails("non-connector indicator")

    def test_reenabled_run_on_open_rejected(self):
        self.after.metadata.find("LVSR/Section/Execution").set("RunOnOpen", "1")
        self.hook_fails("must not run")

    def test_self_reference_replaced_with_other_vi_label_rejected(self):
        node(self.after.bd, "ctlRefConst", "37793").find(
            "label/textRec/text"
        ).text = '"other VI"'
        self.hook_fails("self-VI reference")

    def test_application_reference_instead_of_self_vi_rejected(self):
        types = Types(self.after.metadata)
        descriptor = types.flat[types.top[types.shift + 4111 - 1]]
        descriptor.set("CtlFlags", "0x0001")
        self.hook_fails("self-VI Server")

    def test_psp_write_inside_new_frame_rejected(self):
        node(self.after.bd, "iUse", "18502").set("class", "sharedVariableDynamicWrite")
        self.hook_fails("unexpected operation")

    def test_changed_original_psp_write_primitive_rejected(self):
        node(self.after.bd, "sharedVariableDynamicWrite", "24576").set(
            "class", "sharedVariableDynamicRead"
        )
        with self.assertRaisesRegex(AssertionError, "existing object"):
            validate_preservation(self.before, self.after)

    def test_changed_original_local_direction_rejected(self):
        dco = node(self.after.bd, "gRef", "14489").find("termList/*/dco")
        local = dco.find("objFlags")
        if local is None:
            local = ET.SubElement(dco, "objFlags")
            local.text = "1"
        else:
            local.text = "0" if local.text == "1" else "1"
        with self.assertRaisesRegex(AssertionError, "existing object"):
            validate_preservation(self.before, self.after)

    def test_changed_pressure_field_rejected_by_preservation(self):
        node(self.after.bd, "nMux", "21214").find(
            "termList/*[@uid='72069']/dco/i"
        ).text = "9"
        with self.assertRaisesRegex(AssertionError, "existing object"):
            validate_preservation(self.before, self.after)

    def test_unreviewed_object_flag_rejected(self):
        node(self.after.bd, "gRef", "14489").find("objFlags").text = "513"
        with self.assertRaisesRegex(AssertionError, "unreviewed native-editor"):
            validate_preservation(self.before, self.after)

    def test_actual_event_specification_change_rejected(self):
        event = node(self.after.bd, "eventStruct", "43")
        event.find("EventNodeEvents/*/source").text = "3"
        with self.assertRaisesRegex(AssertionError, "existing object"):
            validate_preservation(self.before, self.after)


if __name__ == "__main__":
    unittest.main()
