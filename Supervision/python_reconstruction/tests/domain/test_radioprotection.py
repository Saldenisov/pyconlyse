import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from supervision_reconstruction.domain.radioprotection import (
    EpcState,
    RadioprotectionGraph,
    update_radioprotection_graph,
)


def _epc(
    *,
    arret=False,
    veille=False,
    pretir=False,
    tir=False,
    arret_not_veille=False,
    pretir_not_veille=False,
    tir_not_pretir=False,
):
    return EpcState(
        arret_ok=arret,
        veille_ok=veille,
        pretir_ok=pretir,
        tir_ok=tir,
        arret_not_veille=arret_not_veille,
        pretir_not_veille=pretir_not_veille,
        tir_not_pretir=tir_not_pretir,
    )


class RadioprotectionTests(unittest.TestCase):
    def test_non_tenth_btim_keeps_stored_output_not_incoming_graph(self) -> None:
        previous = RadioprotectionGraph(1.0, 2.0, 3.0, 4.0)
        stored = RadioprotectionGraph(11.0, 12.0, 13.0, 14.0)
        result = update_radioprotection_graph(
            19.0, previous, False, _epc(tir=True), 99.0, stored_output=stored
        )

        self.assertFalse(result.sampled)
        self.assertIs(result.graph, stored)
        self.assertEqual(result.state_bitmask, 8)

    def test_tenth_btim_maps_all_one_hot_epc_states_to_legacy_ordinates(self) -> None:
        previous = RadioprotectionGraph(9.0, 9.0, 9.0, 9.0)
        cases = (
            ("arret", _epc(arret=True), 0.0),
            ("veille", _epc(veille=True), 1.0),
            ("pretir", _epc(pretir=True), 2.0),
            ("tir", _epc(tir=True), 3.0),
        )

        for _name, epc, ordinate in cases:
            result = update_radioprotection_graph(20.0, previous, True, epc, 7.5)
            self.assertTrue(result.sampled)
            self.assertTrue(result.state_is_one_hot)
            self.assertEqual(result.graph.sommateur, 1.0)
            self.assertEqual(result.graph.tir_pretir_veille_arret, ordinate)
            self.assertEqual(result.graph.vide_section, 7.5)
            self.assertEqual(result.graph.transition, -1.0)

    def test_zero_and_multibit_states_retain_incoming_ordinate_but_are_invalid(
        self,
    ) -> None:
        previous = RadioprotectionGraph(0.0, 42.0, 0.0, 0.0)
        for epc, expected_mask in ((_epc(), 0), (_epc(arret=True, tir=True), 9)):
            result = update_radioprotection_graph(0.0, previous, False, epc, 3.0)
            self.assertEqual(result.graph.tir_pretir_veille_arret, 42.0)
            self.assertFalse(result.state_is_one_hot)
            self.assertEqual(result.state_bitmask, expected_mask)

    def test_transition_field_keeps_previous_ordinate_only_when_transition_is_detected(
        self,
    ) -> None:
        previous = RadioprotectionGraph(0.0, 99.0, 0.0, 0.0)
        result = update_radioprotection_graph(
            10.0,
            previous,
            False,
            _epc(pretir=True, pretir_not_veille=True),
            2.5,
        )

        self.assertEqual(result.graph.sommateur, 0.0)
        self.assertEqual(result.graph.tir_pretir_veille_arret, 2.0)
        self.assertEqual(result.graph.transition, 99.0)

    def test_unsampled_call_without_stored_state_is_refused(self):
        with self.assertRaisesRegex(ValueError, "explicit stored_output"):
            update_radioprotection_graph(
                1.0, RadioprotectionGraph(0, 2, 0, 0), False, _epc(), 1
            )

    def test_exhaustive_state_and_transition_combinations(self):
        for incoming in (-1.0, 0.0, 2.0, 42.0):
            for mask in range(16):
                for transition in range(8):
                    epc = EpcState(
                        *(bool(mask & (1 << i)) for i in range(4)),
                        *(bool(transition & (1 << i)) for i in range(3)),
                    )
                    previous = RadioprotectionGraph(7, incoming, 8, 9)
                    result = update_radioprotection_graph(20.0, previous, True, epc, 10)
                    with self.subTest(
                        incoming=incoming, mask=mask, transition=transition
                    ):
                        self.assertEqual(
                            result.graph.tir_pretir_veille_arret,
                            {1: 0.0, 2: 1.0, 4: 2.0, 8: 3.0}.get(mask, incoming),
                        )
                        self.assertEqual(
                            result.graph.transition, incoming if transition else -1.0
                        )
                        self.assertEqual(result.state_is_one_hot, mask in (1, 2, 4, 8))

    def test_default_passthrough_is_pinned_to_original_xml_and_native_capture(self):
        supervision = Path(__file__).resolve().parents[3]
        proof = json.loads(
            (
                supervision / "analysis/lvkit_eval/parser_release_20261003/06.json"
            ).read_text()
        )
        self.assertEqual(
            proof["sha256"],
            "25D72D2432462638F26E71F8E02614A02CA5174D7008E7E8116B8102C205718D",
        )
        xml = Path(proof["xml"][0]["path"])
        self.assertEqual(
            hashlib.sha256(xml.read_bytes()).hexdigest().upper(),
            proof["xml"][0]["sha256"],
        )
        root = ET.parse(xml).getroot()
        case = next(n for n in root.iter() if n.get("uid") == "609")
        frame = case.find("diagramList")[0]
        pairs = [
            [n.get("uid") for n in s.find("termList")]
            for s in frame.findall("signalList/SL__arrayElement")
        ]
        self.assertEqual(pairs, [["245", "2016"]])
        self.assertIsNone(case.find("SelectDefaultCase"))
        capture = (
            supervision
            / "analysis/screenshots"
            / "2_SUP_Graph_Radioprot_outer_true_state_0_default_lower_true_full.png"
        )
        self.assertEqual(
            hashlib.sha256(capture.read_bytes()).hexdigest().upper(),
            "637C97CD44D0B7F19CC3A22DC627F46E8962DB64BD428CB43321CEEC4B7BC2DC",
        )
