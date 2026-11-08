"""Legacy descriptor boundaries and source-qualified candidate refusal controls."""
import hashlib
import json
import os
import struct
import unittest
import xml.etree.ElementTree as ET

from tools.resolve_legacy_labview_types import (
    LegacyTypeGap, decode_legacy_dthp, extract_legacy_resources,
    inspect_primitive_dco, corroborate_exact_port,
)
from tools.decode_labview_pointer_heap import decode_pointer_heap, PointerHeapGap

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKETS = os.path.join(REPO, 'Supervision', 'integration_analysis', 'orchestrator')
SID = 'LOCAL-08dbe928087239b70b24b358'


def load(path):
    with open(long_path(path), 'rb') as stream:
        return json.loads(stream.read().decode('utf-8'))


def long_path(path):
    path = os.path.abspath(path)
    prefix = chr(92) * 2 + '?' + chr(92)
    return prefix + path if os.name == 'nt' and not path.startswith(prefix) else path


def checked(pin):
    with open(long_path(pin['path']), 'rb') as stream:
        raw = stream.read()
    if len(raw) != pin['bytes'] or hashlib.sha256(raw).hexdigest().upper() != pin['sha256']:
        raise AssertionError('Fixture pin disagreement: ' + pin['path'])
    return raw


def original_fixture():
    heap = load(os.path.join(PACKETS, 'original_heap_followup_20261009', 'SOURCE_INPUTS.json'))
    row = next(r for r in heap['rows'] if r['source_id'] == SID and r['block'] == 'BDHP')
    original = checked(row['original'])
    prior = load(os.path.join(PACKETS, 'original_primitive_followup_20261009', 'AUDIT.json'))
    prior_row = next(r for r in prior['rows'] if r['source_id'] == SID)
    model = load(prior_row['model']['path'])
    checked(prior_row['model'])
    legacy = load(os.path.join(PACKETS, 'refusal_followup_20261008', 'NATIVE_LEGACY.json'))
    member = next(m for m in legacy['members'] if SID in m['original_source_ids_by_raw_name'])
    modern = checked(member['binary'])
    xml = checked(prior_row['resaved_bd_xml'])
    correspondences = {}
    for node in model['nodes']:
        candidates = node['matching_resaved_candidates']
        if len(candidates) != 1:
            raise AssertionError('Selected fixture lost unique signature candidate')
        saved = candidates[0]
        for port in node['ports']:
            matches = [p for p in saved['ports'] if p['parameter_index'] == port['parameter_index'] and p['output_flag_projection'] == port['output_flag_projection']]
            if len(matches) != 1:
                raise AssertionError('Selected fixture lost signature port candidate')
            target = matches[0]
            correspondences[port['dco_offset']] = dict(
                strength='G44_OPERATION_SLOT_OUTPUT_SIGNATURE_MULTISET_CANDIDATE',
                original_source_sha256=row['original']['sha256'], original_BDHP_sha256=row['payload']['sha256'],
                resaved_source_sha256=member['binary']['sha256'], resaved_BD_xml_sha256=prior_row['resaved_bd_xml']['sha256'],
                primitive_chunk_offset=node['offset'], primitive_operation_id=node['prim_res_id'],
                parameter_index=port['parameter_index'], output_flag_projection=port['output_flag_projection'],
                resaved_node_uid=saved['resaved_node_uid'], resaved_terminal_uid=target['resaved_terminal_uid'],
                resaved_dco_uid=target['resaved_dco_uid'], original_UID_correspondence_qualified=False,
                historical_model_sha256=prior_row['model']['sha256'])
    return original, modern, xml, correspondences


def descriptor_fixture(alias=False):
    descriptor = bytes.fromhex('000E4032FFFFFFFF047061746800')
    root = bytearray(164)
    struct.pack_into('>3I', root, 0, 164, 0, 126)
    part = struct.pack('>3I', 30, 0, 131) + descriptor + b'\x00\x00'
    count = 2 if alias else 1
    table_offset = 56 + len(root) + len(part)
    table = struct.pack('>4I', 20 + count * 4, 0, 7, count) + struct.pack('>I', 232) * count + b'\x00' * 4
    struct.pack_into('>I', root, 116, table_offset + 12)
    raw = bytearray(56) + root + part + table + struct.pack('>2I', 9, 0)
    raw[4:8] = b'DTHP'
    for offset, value in ((8, 68), (16, 56), (20, 56), (24, len(raw) - 8), (32, len(raw) - 1)):
        struct.pack_into('>I', raw, offset, value)
    return bytes(raw)


class LegacyTypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, cls.modern, cls.xml, cls.links = original_fixture()
        cls.resources = extract_legacy_resources(cls.original)

    def test_original_complete_envelopes_and_alias_slots(self):
        model = decode_legacy_dthp(self.resources['blocks']['DTHP']['payload'])
        self.assertEqual(len(model['descriptors']), 21)
        self.assertEqual(model['slot_table']['count'], 34)
        self.assertEqual(sum(d['raw_low_bits'] == 2 for d in model['descriptors']), 11)
        self.assertFalse(model['complete_type_schema_qualified'])
        self.assertFalse(model['native_type_binding_qualified'])
        alias = decode_legacy_dthp(descriptor_fixture(alias=True))
        self.assertEqual([s['saved_slot_one_based'] for s in alias['slot_table']['slots']], [1, 2])
        self.assertEqual(alias['slot_table']['slots'][0]['raw_target_data_address'], alias['slot_table']['slots'][1]['raw_target_data_address'])

    def test_four_correspondences_exact_bytes_without_native_promotion(self):
        expected = {5268: (29, 22, 37), 5448: (30, 19, 37), 5532: (31, 20, 69), 5636: (32, 21, 38)}
        for offset, values in expected.items():
            result = corroborate_exact_port(self.original, offset, self.modern, self.xml, self.links[offset])
            self.assertEqual((result['raw_dco_word24'], result['resaved_heap_type_id'], result['resaved_descriptor']['flat_index']), values)
            self.assertEqual(result['status'], 'CORROBORATED_METADATA_CANDIDATE')
            self.assertTrue(result['exact_descriptor_bytes_equal'])
            for key in ('actual_type_binding_qualified', 'native_type_binding_qualified', 'original_UID_correspondence_qualified', 'wire_routing_qualified', 'whole_body_qualified', 'native_runtime_equivalence'):
                self.assertFalse(result[key])

    def test_zero_based_counterexample_changes_complete_descriptor(self):
        original = decode_legacy_dthp(self.resources['blocks']['DTHP']['payload'])
        selected = inspect_primitive_dco(self.original, 5448)
        wrong = original['slot_table']['slots'][selected['raw_dco_word24']]
        self.assertNotEqual(wrong['descriptor_sha256'], selected['descriptor']['descriptor_sha256'])

    def test_every_descriptor_fixture_and_original_dthp_prefix_refused(self):
        for raw in (descriptor_fixture(), self.resources['blocks']['DTHP']['payload']):
            for end in range(len(raw)):
                with self.assertRaises(LegacyTypeGap):
                    decode_legacy_dthp(raw[:end])

    def test_trailing_and_unknown_root_or_descriptor_layouts_refused(self):
        raw = descriptor_fixture()
        cases = [raw + b'\x00' * 4]
        for offset, value, fmt in ((220, 31, '>I'), (228, 132, '>I'), (232, 0, '>H'),
                                   (232, 16, '>H'), (58, 1, '>B'), (68, 1, '>I'),
                                   (246, 1, '>B'), (260, 0, '>I'), (264, 56, '>I')):
            altered = bytearray(raw)
            struct.pack_into(fmt, altered, offset, value)
            cases.append(bytes(altered))
        for altered in cases:
            with self.assertRaises(LegacyTypeGap):
                decode_legacy_dthp(altered)

    def test_duplicate_table_or_non_descriptor_target_refused(self):
        raw = bytearray(descriptor_fixture())
        table = bytes(raw[248:272])
        raw[272:272] = table
        for offset, value in ((24, len(raw) - 8), (32, len(raw) - 1)):
            struct.pack_into('>I', raw, offset, value)
        with self.assertRaises(LegacyTypeGap):
            decode_legacy_dthp(bytes(raw))
        for address in (0, 220, 68, 260, 999999):
            raw = bytearray(descriptor_fixture())
            struct.pack_into('>I', raw, 264, address)
            with self.assertRaises(LegacyTypeGap):
                decode_legacy_dthp(bytes(raw))

    def test_generic_bdhp_lowbits_two_still_refused(self):
        raw = bytearray(self.resources['blocks']['BDHP']['payload'])
        struct.pack_into('>I', raw, 56, struct.unpack_from('>I', raw, 56)[0] | 2)
        with self.assertRaises(PointerHeapGap):
            decode_pointer_heap(bytes(raw))

    def test_zero_negative_bool_unknown_and_cross_heap_offsets_refused(self):
        for value in (True, -1, 0, 1212, 5269, 6000000):
            with self.assertRaises(LegacyTypeGap):
                inspect_primitive_dco(self.original, value)
        offset = self.resources['blocks']['BDHP']['resource_file_offset']
        for relative, value in ((5268 + 20, 1224), (5268 + 20, 5280), (5268 + 24, 0), (5268 + 24, 35)):
            raw = bytearray(self.original)
            struct.pack_into('>I', raw, offset + relative, value)
            with self.assertRaises(LegacyTypeGap):
                inspect_primitive_dco(bytes(raw), 5268)

    def test_container_version_trailing_duplicate_and_source_receipts_refused(self):
        version_offset = self.resources['blocks']['LVSR']['resource_file_offset']
        raw = bytearray(self.original)
        struct.pack_into('>I', raw, version_offset, 0x07108000)
        for value in (bytes(raw), self.original + b'\x00', self.original[:32]):
            with self.assertRaises(LegacyTypeGap):
                extract_legacy_resources(value)
        raw = bytearray(self.original)
        info = struct.unpack_from('>I', raw, 16)[0]
        base = info + struct.unpack_from('>I', raw, info + 44)[0]
        raw[base + 16:base + 20] = raw[base + 4:base + 8]
        with self.assertRaises(LegacyTypeGap):
            extract_legacy_resources(bytes(raw))
        for field, value in (('strength', 'NATIVE_TYPE_PROOF'), ('original_source_sha256', '0' * 64),
                             ('primitive_chunk_offset', 5396), ('resaved_node_uid', '0'),
                             ('resaved_terminal_uid', '0'), ('resaved_dco_uid', '0')):
            link = dict(self.links[5268])
            link[field] = value
            with self.assertRaises(LegacyTypeGap):
                corroborate_exact_port(self.original, 5268, self.modern, self.xml, link)

    def test_multiple_or_malformed_selected_type_and_unequal_bytes_refused(self):
        selected = b'<typeDesc>TypeID(22)</typeDesc>'
        for replacement in (selected + selected, b'<typeDesc />'):
            xml = self.xml.replace(selected, replacement, 1)
            link = dict(self.links[5268])
            link['resaved_BD_xml_sha256'] = hashlib.sha256(xml).hexdigest().upper()
            with self.assertRaises(LegacyTypeGap):
                corroborate_exact_port(self.original, 5268, self.modern, xml, link)
        for replacement in (b'TypeID(0)', b'TypeID(019)', b'TypeID(999999)'):
            xml = self.xml.replace(b'TypeID(22)', replacement, 1)
            link = dict(self.links[5268])
            link['resaved_BD_xml_sha256'] = hashlib.sha256(xml).hexdigest().upper()
            with self.assertRaises(LegacyTypeGap):
                corroborate_exact_port(self.original, 5268, self.modern, xml, link)
        xml = self.xml.replace(b'TypeID(22)', b'TypeID(20)', 1)
        link = dict(self.links[5268])
        link['resaved_BD_xml_sha256'] = hashlib.sha256(xml).hexdigest().upper()
        with self.assertRaises(LegacyTypeGap):
            corroborate_exact_port(self.original, 5268, self.modern, xml, link)

    def test_scalar_nested_children_or_unknown_attributes_refused(self):
        for field, uid, offset in (('typeDesc', '227', 5268), ('objFlags', '227', 5268),
                                   ('primResID', '222', 5268), ('parmIndex', '233', 5532)):
            for mutation in ('nested', 'attribute'):
                tree = ET.fromstring(self.xml)
                owner = next(n for n in tree.iter() if n.get('class') and n.get('uid') == uid)
                target = owner.find(field)
                if mutation == 'nested':
                    ET.SubElement(target, 'UnknownNestedField')
                else:
                    target.set('UnknownAttribute', '1')
                xml = ET.tostring(tree, encoding='utf-8')
                link = dict(self.links[offset])
                link['resaved_BD_xml_sha256'] = hashlib.sha256(xml).hexdigest().upper()
                with self.assertRaises(LegacyTypeGap):
                    corroborate_exact_port(self.original, offset, self.modern, xml, link)

    def test_counted_terminal_list_malformed_counts_and_foreign_records_refused(self):
        for count in ('999', '0', '-1', '', 'x', '+1', '01', None, '1 '):
            tree = ET.fromstring(self.xml)
            node = next(n for n in tree.iter() if n.get('class') == 'prim' and n.get('uid') == '222')
            terminal_list = node.find('termList')
            if count is None:
                del terminal_list.attrib['elements']
            else:
                terminal_list.set('elements', count)
            xml = ET.tostring(tree, encoding='utf-8')
            link = dict(self.links[5268])
            link['resaved_BD_xml_sha256'] = hashlib.sha256(xml).hexdigest().upper()
            with self.assertRaises(LegacyTypeGap):
                corroborate_exact_port(self.original, 5268, self.modern, xml, link)
        for mutation in ('unknown_child', 'uid_reference', 'foreign_incomplete', 'foreign_complete'):
            tree = ET.fromstring(self.xml)
            node = next(n for n in tree.iter() if n.get('class') == 'prim' and n.get('uid') == '222')
            terminal_list = node.find('termList')
            if mutation == 'unknown_child':
                ET.SubElement(terminal_list, 'UnknownNestedField')
            elif mutation == 'uid_reference':
                ET.SubElement(terminal_list, 'SL__arrayElement', {'uid': '228'})
            elif mutation == 'foreign_incomplete':
                ET.SubElement(terminal_list, 'SL__arrayElement', {'class': 'term', 'uid': '99999'})
            else:
                foreign = ET.fromstring(ET.tostring(terminal_list[0], encoding='utf-8'))
                foreign.set('uid', '99999')
                foreign.find('dco').set('uid', '99998')
                terminal_list.append(foreign)
            terminal_list.set('elements', str(len(terminal_list)))
            xml = ET.tostring(tree, encoding='utf-8')
            link = dict(self.links[5268])
            link['resaved_BD_xml_sha256'] = hashlib.sha256(xml).hexdigest().upper()
            with self.assertRaises(LegacyTypeGap):
                corroborate_exact_port(self.original, 5268, self.modern, xml, link)

    def test_complete_signature_and_selected_primitive_index_refused(self):
        for uid, field, value, selected in (('236', 'parmIndex', '999', 5532),
                                           ('227', 'primIndex', '999', 5268)):
            tree = ET.fromstring(self.xml)
            owner = next(n for n in tree.iter() if n.get('class') and n.get('uid') == uid)
            owner.find(field).text = value
            xml = ET.tostring(tree, encoding='utf-8')
            link = dict(self.links[selected])
            link['resaved_BD_xml_sha256'] = hashlib.sha256(xml).hexdigest().upper()
            with self.assertRaises(LegacyTypeGap):
                corroborate_exact_port(self.original, selected, self.modern, xml, link)

    def test_selected_scalar_record_and_counted_list_mixed_tails_refused(self):
        for uid, field in (('227', 'typeDesc'), ('228', 'dco'), ('222', 'termList'),
                           ('228', None), ('227', None)):
            tree = ET.fromstring(self.xml)
            owner = next(n for n in tree.iter() if n.get('class') and n.get('uid') == uid)
            target = owner.find(field) if field is not None else owner
            target.tail = 'UNKNOWN_MIXED_TEXT'
            xml = ET.tostring(tree, encoding='utf-8')
            link = dict(self.links[5268])
            link['resaved_BD_xml_sha256'] = hashlib.sha256(xml).hexdigest().upper()
            with self.assertRaises(LegacyTypeGap):
                corroborate_exact_port(self.original, 5268, self.modern, xml, link)


if __name__ == '__main__':
    unittest.main()
