"""Offline mutations of saved native telemetry helpers; no UI/network/VI run."""

import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from validate_acq_modulator_start_event_guards import checked_root  # noqa: E402
from validate_acq_shared_state_helpers import (  # noqa: E402
    BANKS,
    COLLECTOR,
    QUEUE,
    Export,
    audit,
    node,
    validate,
    validate_pressure_inclusion,
)

NATIVE = Path("C:/dev/ELYSE-ACQ-telemetry/2026-10-13/shared_state_native_helpers")
LIBRARY = (
    ROOT / "Supervision/extracted/PILOTAGE_ELYSE_SUP/SUPERVISION_VIs/SUPERVISION.lvlib"
)
MAIN_FP = ROOT / ".tmp/acq_original_diagram_census_20261001/0_ACQ_ELYSE/vi_FPHb.xml"
MAIN_ARCHIVE = (
    ROOT / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
)


@unittest.skipUnless(
    (NATIVE / "export" / COLLECTOR / "vi.xml").is_file()
    and LIBRARY.is_file()
    and MAIN_FP.is_file(),
    "requires local, hash-pinned native shared-state helper evidence",
)
class SharedStateHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = (
            Export(NATIVE / "export" / COLLECTOR),
            Export(NATIVE / "export" / QUEUE),
            ET.parse(LIBRARY).getroot(),
            ET.parse(MAIN_FP).getroot(),
        )

    def setUp(self):
        self.collector, self.queue, self.library, self.main_fp = deepcopy(self.evidence)

    def check(self):
        return validate(self.collector, self.queue, self.library, self.main_fp)

    def test_pinned_native_pair_passes_without_delivery_claim(self):
        report = audit(NATIVE, LIBRARY, MAIN_FP)
        self.assertEqual(report["bank_count"], 27)
        self.assertEqual(report["banks"], list(BANKS))
        self.assertEqual(report["queue"]["enqueue_primitive"], 9130)
        for flag in (
            "main_timeout_integrated",
            "telemetry_complete",
            "native_vi_executed",
            "hardware_access",
            "psp_access_in_helpers",
            "network_access_in_helpers",
        ):
            self.assertFalse(report[flag])

    def test_regular_enqueue_rejected(self):
        node(self.queue.bd, "prim", "222").find("primResID").text = "9111"
        with self.assertRaisesRegex(AssertionError, "operation set"):
            self.check()

    def test_queue_size_1000_rejected(self):
        node(self.queue.bd, "bDConstDCO", "90").find("ConstValue").text = "000003E8"
        with self.assertRaisesRegex(AssertionError, "maximum"):
            self.check()

    def test_shared_old_queue_name_rejected(self):
        value = b"ELYSE_ACQ_TELEMETRY_V1"
        node(self.queue.bd, "bDConstDCO", "125").find("ConstValue").text = (
            len(value).to_bytes(4, "big") + value
        ).hex()
        with self.assertRaisesRegex(AssertionError, "queue name"):
            self.check()

    def test_create_if_missing_rejected(self):
        node(self.queue.bd, "bDConstDCO", "158").find("ConstValue").text = "0001"
        with self.assertRaisesRegex(AssertionError, "create"):
            self.check()

    def test_force_destroy_rejected(self):
        node(self.queue.bd, "bDConstDCO", "628").find("ConstValue").text = "0001"
        with self.assertRaisesRegex(AssertionError, "force-destroy"):
            self.check()

    def test_set_control_value_rejected(self):
        node(self.collector.bd, "invokeNode", "253").find(
            "methName"
        ).text = '"Ctrl Val.Set"'
        with self.assertRaisesRegex(AssertionError, "read-only"):
            self.check()

    def test_psp_write_operation_rejected(self):
        ET.SubElement(
            self.collector.bd.find("root/zPlaneList"),
            "SL__arrayElement",
            {"class": "sharedVariableDynamicWrite", "uid": "new-writer"},
        )
        with self.assertRaisesRegex(AssertionError, "unexpected operation"):
            self.check()

    def test_tcp_operation_rejected(self):
        ET.SubElement(
            self.queue.bd.find("root/zPlaneList"),
            "SL__arrayElement",
            {"class": "prim", "uid": "new-tcp"},
        )
        with self.assertRaisesRegex(AssertionError, "operation set"):
            self.check()

    def test_wrong_bank_rejected(self):
        value = node(self.collector.bd, "bDConstDCO", "230").find("ConstValue")
        value.text = value.text.replace("43324E493630373145", "43314E493630373145")
        with self.assertRaisesRegex(AssertionError, "whitelist"):
            self.check()

    def test_missing_individual_read_error_wire_rejected(self):
        diagram = node(self.collector.bd, "diag", "324")
        signal = next(
            w
            for w in diagram.findall("signalList/*")
            if tuple(t.get("uid") for t in w.findall("termList/*")) == ("268", "444")
        )
        diagram.find("signalList").remove(signal)
        with self.assertRaisesRegex(AssertionError, "wire topology"):
            self.check()

    def test_output_autoindexing_disabled_rejected(self):
        node(self.collector.bd, "lpTun", "575").find("TunnelType").text = "00"
        with self.assertRaisesRegex(AssertionError, "auto-indexing"):
            self.check()

    def test_run_on_open_rejected(self):
        self.collector.metadata.find("LVSR/Section/Execution").set("RunOnOpen", "1")
        with self.assertRaisesRegex(AssertionError, "execution flag"):
            self.check()

    def test_missing_library_bank_rejected(self):
        missing = next(
            n for n in self.library.findall("Item") if n.get("Name") == "DPS"
        )
        self.library.remove(missing)
        with self.assertRaisesRegex(AssertionError, "library catalog"):
            self.check()

    def test_counter_control_alias_missing_rejected(self):
        for part in self.main_fp.findall(".//*[@class='fPDCO']/ddo/partsList/*"):
            if (
                part.findtext("textRec/text") == '"C10-11 NI6602"'
                and part.findtext("partID") == "16"
            ):
                part.find("textRec/text").text = '"C1011NI6602"'
        with self.assertRaisesRegex(AssertionError, "bank control"):
            self.check()

    def test_cut_queue_error_chain_rejected(self):
        signals = self.queue.bd.find("root/signalList")
        signal = next(
            w
            for w in signals
            if tuple(t.get("uid") for t in w.findall("termList/*")) == ("72", "239")
        )
        signals.remove(signal)
        with self.assertRaisesRegex(AssertionError, "wire topology"):
            self.check()


@unittest.skipUnless(
    (NATIVE / "export" / COLLECTOR / "vi.xml").is_file() and MAIN_ARCHIVE.is_file(),
    "requires pinned native pressure evidence",
)
class SharedStatePressureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collector = Export(NATIVE / "export" / COLLECTOR)
        cls.main_bd = checked_root(MAIN_ARCHIVE)

    def test_existing_tpg_pressure_included_without_second_poll(self):
        report = validate_pressure_inclusion(self.collector, self.main_bd)
        self.assertEqual(report["bank"], "VAM-A")
        self.assertEqual(report["zero_based_fields"], [10, 11, 20])
        self.assertFalse(report["new_instrument_poll"])
        self.assertFalse(report["sensor_status_included"])
        self.assertFalse(report["transport_delivery_verified"])

    def test_changed_pressure_field_rejected(self):
        main = deepcopy(self.main_bd)
        node(main, "nMux", "21214").find("termList/*[@uid='72069']/dco/i").text = "9"
        with self.assertRaisesRegex(AssertionError, "field index"):
            validate_pressure_inclusion(self.collector, main)

    def test_missing_vam_bank_rejected(self):
        collector = deepcopy(self.collector)
        value = node(collector.bd, "bDConstDCO", "230").find("ConstValue")
        value.text = value.text.replace("56414D2D41", "56414D2D58")
        with self.assertRaisesRegex(AssertionError, "whitelist"):
            validate_pressure_inclusion(collector, self.main_bd)


if __name__ == "__main__":
    unittest.main()
