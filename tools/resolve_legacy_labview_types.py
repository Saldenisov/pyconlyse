"""Bounded LV7 pointer-heap descriptor envelopes and exact byte corroboration.

This separate reader does not relax the BDHP decoder. Legacy descriptors remain
opaque unless their complete bytes match a separately pinned resaved descriptor.
The port correspondence is inherited signature evidence, not original UID,
native type binding, conversion equivalence, or executable business coverage.
Compatible with Python 3.4; no native imports or source execution.
"""
import binascii
import hashlib
import re
import struct
import xml.etree.ElementTree as ET
import zlib

from tools.decode_labview_pointer_heap import decode_pointer_heap, PointerHeapGap


class LegacyTypeGap(ValueError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest().upper()


def _hex(raw):
    return binascii.hexlify(raw).decode('ascii').upper()


def _take(raw, offset, size):
    if type(offset) is not int or type(size) is not int or offset < 0 or size < 0 or offset + size > len(raw):
        raise LegacyTypeGap('Truncated or invalid resource field')
    return raw[offset:offset + size]


def _u32(raw, offset):
    return struct.unpack('>I', _take(raw, offset, 4))[0]


def _u16(raw, offset):
    return struct.unpack('>H', _take(raw, offset, 2))[0]


def _u2p2(raw, offset):
    first = _u16(raw, offset)
    if first & 0x8000:
        return ((first & 0x7fff) << 16) | _u16(raw, offset + 2), offset + 4
    return first, offset + 2


def _scalar(parent, name, required=False):
    """Selected saved scalar profile: one text leaf, no unknown attributes."""
    fields = parent.findall(name)
    if not fields:
        if required:
            raise LegacyTypeGap('Missing selected scalar field: ' + name)
        return None
    if len(fields) != 1:
        raise LegacyTypeGap('Repeated selected scalar field: ' + name)
    field = fields[0]
    if field.attrib or len(field) or field.text is None or not field.text or field.tail and field.tail.strip():
        raise LegacyTypeGap('Unknown selected scalar leaf layout: ' + name)
    return field.text


def _decimal(text, field):
    if type(text) is not str or re.match(r'(0|[1-9][0-9]*)\Z', text) is None:
        raise LegacyTypeGap('Malformed selected decimal field: ' + field)
    return int(text, 10)


def _selected_record(element, tag, classname):
    if element.tag != tag or set(element.attrib) != {'class', 'uid'} or element.get('class') != classname:
        raise LegacyTypeGap('Unknown selected saved record layout')
    uid = element.get('uid')
    if re.match(r'[0-9]+\Z', uid or '') is None:
        raise LegacyTypeGap('Malformed selected saved record UID')
    if element.text and element.text.strip():
        raise LegacyTypeGap('Mixed text in selected saved record')
    if element.tail and element.tail.strip() or any(child.tail and child.tail.strip() for child in element):
        raise LegacyTypeGap('Mixed child tail in selected saved record')


def _counted_terms(node, tree):
    lists = node.findall('termList')
    if len(lists) != 1:
        raise LegacyTypeGap('Selected resaved term-list definition is absent or repeated')
    elements = lists[0]
    if set(elements.attrib) != {'elements'} or elements.text and elements.text.strip():
        raise LegacyTypeGap('Unknown selected counted terminal-list layout')
    count = _decimal(elements.get('elements'), 'termList.elements')
    if not 0 < count <= 4095 or count != len(elements):
        raise LegacyTypeGap('Selected terminal-list count disagrees with saved entries')
    seen_terms, seen_parameters = set(), set()
    for terminal in elements:
        _selected_record(terminal, 'SL__arrayElement', 'term')
        uid = terminal.get('uid')
        if uid in seen_terms or len([n for n in tree.iter() if n.get('class') and n.get('uid') == uid]) != 1:
            raise LegacyTypeGap('Duplicate selected counted terminal definition')
        seen_terms.add(uid)
        if any(child.tag not in {'dco', 'objFlags'} for child in terminal) or len(terminal.findall('dco')) != 1:
            raise LegacyTypeGap('Unknown selected terminal parameter layout')
        terminal_flags = _scalar(terminal, 'objFlags')
        if terminal_flags is not None:
            _decimal(terminal_flags, 'terminal.objFlags')
        parameter = terminal.find('dco')
        _selected_record(parameter, 'dco', 'parm')
        parameter_uid = parameter.get('uid')
        if parameter_uid in seen_parameters or len([n for n in tree.iter() if n.get('class') and n.get('uid') == parameter_uid]) != 1:
            raise LegacyTypeGap('Duplicate selected counted parameter definition')
        seen_parameters.add(parameter_uid)
    return list(elements)


def _resources(raw, selected):
    if type(raw) is not bytes or not 64 <= len(raw) <= 64 * 1024 * 1024:
        raise LegacyTypeGap('Unqualified RSRC byte input')
    if _take(raw, 0, 16) != b'RSRC\r\n\x00\x03LVINLBVW':
        raise LegacyTypeGap('Unqualified RSRC container profile')
    info, info_size, data, data_size = struct.unpack('>4I', _take(raw, 16, 16))
    if data != 32 or info != data + data_size or info + info_size != len(raw):
        raise LegacyTypeGap('RSRC spans do not consume input exactly')
    _take(raw, info, info_size)
    base = info + _u32(raw, info + 44)
    count = _u32(raw, base) + 1
    if not 0 < count <= 4096 or base + 4 + 12 * count > info + info_size:
        raise LegacyTypeGap('Unbounded RSRC directory')
    result = {}
    identifiers = set()
    for index in range(count):
        ident, sections, offset = struct.unpack('>4sII', _take(raw, base + 4 + 12 * index, 12))
        if ident in identifiers:
            raise LegacyTypeGap('Duplicate RSRC block identity')
        identifiers.add(ident)
        if ident not in selected:
            continue
        if sections != 0:
            raise LegacyTypeGap('Selected resource has repeated sections')
        start = base + offset
        if start < base + 4 + 12 * count or start + 20 > info + info_size:
            raise LegacyTypeGap('Selected section directory is outside metadata')
        section, unused_name, unused_a, relative, unused_b = struct.unpack('>i4I', _take(raw, start, 20))
        if section != 0:
            raise LegacyTypeGap('Selected resource is not section zero')
        length_position = data + relative
        size = _u32(raw, length_position)
        position = length_position + 4
        if length_position < data or not 0 < size <= 8 * 1024 * 1024 or position + size > info:
            raise LegacyTypeGap('Selected resource exceeds data span')
        payload = _take(raw, position, size)
        result[ident.decode('ascii')] = dict(block=ident.decode('ascii'), section=0,
            resource_file_offset=position, bytes=size, sha256=_sha(payload), payload=payload)
    if set(result) != set(x.decode('ascii') for x in selected):
        raise LegacyTypeGap('Missing selected resource')
    spans = sorted((r['resource_file_offset'] - 4, r['resource_file_offset'] + r['bytes']) for r in result.values())
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise LegacyTypeGap('Selected resource spans overlap')
    return result


def extract_legacy_resources(original_vi):
    """Return exact original LV7.0 resources from a single source byte object."""
    blocks = _resources(original_vi, (b'LVSR', b'BDHP', b'FPHP', b'DTHP'))
    version = _u32(blocks['LVSR']['payload'], 0)
    if version != 0x07008000:
        raise LegacyTypeGap('Unsupported original saved version')
    for name in ('BDHP', 'FPHP', 'DTHP'):
        if _take(blocks[name]['payload'], 4, 4) != name.encode('ascii'):
            raise LegacyTypeGap('Resource block and payload heap identity disagree')
    return dict(source_bytes=len(original_vi), source_sha256=_sha(original_vi),
                saved_version_word='07008000', saved_version='7.0.0 release build0', blocks=blocks)


def decode_legacy_dthp(payload):
    """Read the observed DTHP envelope profile; descriptor contents stay opaque.

    Low bits 2 are admitted only in this separate code131 envelope profile,
    with even BE16 lengths and exactly bounded zero padding. Header words and
    aliases retain their original bytes. There is no inferred semantic type.
    """
    if type(payload) is not bytes or not 252 <= len(payload) <= 4 * 1024 * 1024 or len(payload) % 4:
        raise LegacyTypeGap('Unqualified DTHP byte length')
    end = len(payload) - 8
    fixed = {0: 0, 8: 68, 16: 56, 20: 56, 24: end, 28: 0, 32: len(payload) - 1,
             36: 0, 40: 0, 44: 0, 48: 0, 52: 0}
    if payload[4:8] != b'DTHP' or any(_u32(payload, o) != value for o, value in fixed.items()):
        raise LegacyTypeGap('Unqualified DTHP header profile')
    if payload[end:] != b'\x00\x00\x00\x09\x00\x00\x00\x00':
        raise LegacyTypeGap('Unqualified DTHP footer or trailing bytes')
    records = []
    descriptors = []
    position = 56
    root = None
    table = None
    while position < end:
        word = _u32(payload, position)
        size, low = word & ~3, word & 3
        if size < 12 or size > end - position:
            raise LegacyTypeGap('DTHP chunk exceeds body')
        word1, code = _u32(payload, position + 4), _u32(payload, position + 8)
        if word1 != 0:
            raise LegacyTypeGap('Unknown DTHP chunk word1 layout')
        part = _take(payload, position, size)
        record = dict(chunk_offset=position, bytes=size, raw_chunk_word=word, raw_low_bits=low,
                      raw_word1=word1, class_code=code, sha256=_sha(part), raw_hex=_hex(part))
        if position == 56:
            if size != 164 or low != 0 or code != 126:
                raise LegacyTypeGap('Unknown DTHP root layout')
            if any(_u32(payload, position + o) != 0 for o in range(12, 164, 4) if o != 116):
                raise LegacyTypeGap('Unknown DTHP root fields')
            root = record
        elif code == 131 and table is None:
            length = _u16(payload, position + 12)
            if length < 4 or length % 2 or length + 12 > size or (length + 15) & ~3 != size:
                raise LegacyTypeGap('Unqualified BE16 descriptor envelope')
            if low != length % 4 or low not in (0, 2):
                raise LegacyTypeGap('Unknown DTHP descriptor low-bit profile')
            data = _take(payload, position + 12, length)
            padding = payload[position + 12 + length:position + size]
            if any(padding):
                raise LegacyTypeGap('Unqualified DTHP descriptor padding')
            record.update(descriptor_data_address=position + 12, descriptor_bytes=length,
                          descriptor_hex=_hex(data), descriptor_sha256=_sha(data),
                          padding_hex=_hex(padding), semantic_type_qualified=False)
            descriptors.append(record)
        elif code == 7 and table is None and low == 0 and descriptors:
            count = _u32(payload, position + 12)
            if not 0 < count <= 65535 or size != 20 + 4 * count:
                raise LegacyTypeGap('Unqualified DTHP slot-table storage')
            if _take(payload, position + 16 + 4 * count, 4) != b'\x00' * 4:
                raise LegacyTypeGap('Unknown DTHP slot-table tail')
            addresses = {_d['descriptor_data_address']: _d for _d in descriptors}
            slots = []
            for index in range(count):
                value = _u32(payload, position + 16 + 4 * index)
                if value not in addresses:
                    raise LegacyTypeGap('DTHP slot is not an in-heap descriptor boundary')
                target = addresses[value]
                slots.append(dict(saved_slot_one_based=index + 1, raw_target_data_address=value,
                    descriptor_chunk_offset=target['chunk_offset'], descriptor_sha256=target['descriptor_sha256']))
            record.update(slots=slots, count=count, tail_hex='00000000')
            table = record
        else:
            raise LegacyTypeGap('Unknown or repeated DTHP chunk layout')
        records.append(record)
        position += size
    if position != end or root is None or table is None or table['chunk_offset'] + table['bytes'] != end:
        raise LegacyTypeGap('Incomplete DTHP root/descriptor/table partition')
    if _u32(payload, 56 + 116) != table['chunk_offset'] + 12:
        raise LegacyTypeGap('DTHP root table reference disagrees')
    return dict(bytes=len(payload), sha256=_sha(payload), header_hex=_hex(payload[:56]),
                footer_hex=_hex(payload[end:]), records=records, descriptors=descriptors,
                slot_table=table, descriptor_envelopes_qualified=True,
                original_UIDs_qualified=False, complete_type_schema_qualified=False,
                native_type_binding_qualified=False, whole_body_qualified=False)


def inspect_primitive_dco(original_vi, dco_offset):
    """Select source-bound primitive/DCO/terminal facts and a slot candidate."""
    if type(dco_offset) is not int:
        raise LegacyTypeGap('DCO offset must be an integer')
    source = extract_legacy_resources(original_vi)
    bd = source['blocks']['BDHP']['payload']
    try:
        heap = decode_pointer_heap(bd)
    except PointerHeapGap as error:
        raise LegacyTypeGap('BDHP profile refusal: ' + str(error))
    by_offset = {r['offset']: r for r in heap['records']}
    by_data = {r['offset'] + 12: r for r in heap['records'] if r['low_flags'] == 0}
    def target(address, code, size=None):
        value = by_data.get(address)
        if value is None or value['type_code'] != code or size is not None and value['bytes'] != size:
            raise LegacyTypeGap('Primitive reference has wrong in-heap target layout')
        return value
    dco = by_offset.get(dco_offset)
    if dco is None or dco['low_flags'] or dco['type_code'] != 48 or dco['bytes'] != 52:
        raise LegacyTypeGap('Offset outside observed primitive DCO layout')
    owner = target(_u32(bd, dco_offset + 16), 47, 52)
    reference_word = _u32(bd, dco_offset + 20)
    references = target(reference_word, 7)['reference_table']
    if references['count'] != 1:
        raise LegacyTypeGap('DCO terminal-reference count outside selected profile')
    terminal = target(references['links'][0]['raw_value'], 21, 32)
    term_offset = terminal['offset']
    if _u32(bd, term_offset + 16) != owner['offset'] + 12 or _u32(bd, term_offset + 24) != dco_offset + 12:
        raise LegacyTypeGap('Primitive terminal/DCO owner disagreement')
    owner_list = target(_u32(bd, owner['offset'] + 20), 7)['reference_table']
    if sum(x['raw_value'] == term_offset + 12 for x in owner_list['links']) != 1:
        raise LegacyTypeGap('Primitive terminal membership is missing or ambiguous')
    primitive_index = _u16(bd, owner['offset'] + 50)
    if _u16(bd, dco_offset + 48) != primitive_index:
        raise LegacyTypeGap('Original primitive/parameter index disagreement')
    signature = []
    for link in owner_list['links']:
        member = target(link['raw_value'], 21, 32)
        parameter = target(_u32(bd, member['offset'] + 24), 48, 52)
        if _u32(bd, member['offset'] + 16) != owner['offset'] + 12 or _u32(bd, parameter['offset'] + 16) != owner['offset'] + 12:
            raise LegacyTypeGap('Original counted primitive member owner disagreement')
        if _u16(bd, parameter['offset'] + 48) != primitive_index:
            raise LegacyTypeGap('Original counted primitive member index disagreement')
        signature.append(dict(parameter_index=bd[parameter['offset'] + 50], output_flag_projection=_u32(bd, parameter['offset'] + 12) & 1))
    if len(set(p['parameter_index'] for p in signature)) != len(signature):
        raise LegacyTypeGap('Repeated original primitive parameter index')
    types = decode_legacy_dthp(source['blocks']['DTHP']['payload'])
    saved_index = _u32(bd, dco_offset + 24)
    if not 1 <= saved_index <= types['slot_table']['count']:
        raise LegacyTypeGap('Raw DCO+24 outside positive saved slot range')
    slot = types['slot_table']['slots'][saved_index - 1]
    descriptor = next(d for d in types['descriptors'] if d['chunk_offset'] == slot['descriptor_chunk_offset'])
    return dict(original_source_sha256=source['source_sha256'], original_source_bytes=source['source_bytes'],
        original_saved_version_word=source['saved_version_word'], BDHP_sha256=heap['sha256'], DTHP_sha256=types['sha256'],
        primitive_chunk_offset=owner['offset'], primitive_operation_id=_u16(bd, owner['offset'] + 48),
        original_primitive_index=primitive_index, dco_chunk_offset=dco_offset, terminal_chunk_offset=term_offset,
        original_counted_primitive_signature=signature,
        parameter_index_byte50=bd[dco_offset + 50], opaque_parameter_byte51=bd[dco_offset + 51],
        output_flag_projection=_u32(bd, dco_offset + 12) & 1,
        raw_dco_word20=reference_word, word20_observation='IN_HEAP_CODE7_TERMINAL_REFERENCE_TABLE',
        word20_terminal_reference_count=1, word20_terminal_data_address=term_offset + 12,
        raw_dco_word24=saved_index, word24_observation='ONE_BASED_DTHP_SLOT_CANDIDATE',
        candidate_slot=slot, descriptor=descriptor,
        raw_terminal_word20=_u32(bd, term_offset + 20), original_UID=None,
        actual_type_binding_qualified=False, native_type_binding_qualified=False,
        wire_routing_qualified=False, whole_body_qualified=False)


def read_resaved_types(resaved_vi):
    """Bound the independently saved modern VCTP encodings, without retyping."""
    blocks = _resources(resaved_vi, (b'LVSR', b'VCTP', b'DTHP'))
    if _u32(blocks['LVSR']['payload'], 0) != 0x20008000:
        raise LegacyTypeGap('Unsupported corroborating resaved version')
    packed = blocks['VCTP']['payload']
    length = _u32(packed, 0)
    if not 4 <= length <= 4 * 1024 * 1024:
        raise LegacyTypeGap('Unbounded modern type resource')
    try:
        decoder = zlib.decompressobj()
        plain = decoder.decompress(packed[4:], length + 1)
    except zlib.error as error:
        raise LegacyTypeGap('Modern type compression refusal: ' + str(error))
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or len(plain) != length:
        raise LegacyTypeGap('Modern type compression length or tail disagreement')
    count = _u32(plain, 0)
    if not 0 < count <= 4095:
        raise LegacyTypeGap('Unbounded modern flat descriptor count')
    flat = []
    position = 4
    for index in range(count):
        size, unused = _u2p2(plain, position)
        if size < 4:
            raise LegacyTypeGap('Malformed modern descriptor length')
        part = _take(plain, position, size)
        flat.append(dict(flat_index=index, plain_offset=position, bytes=size,
                         sha256=_sha(part), raw_hex=_hex(part)))
        position += size
    top_count, position = _u2p2(plain, position)
    if not 0 < top_count <= 4095:
        raise LegacyTypeGap('Unbounded modern top descriptor count')
    top = []
    for unused in range(top_count):
        value, position = _u2p2(plain, position)
        if value >= len(flat):
            raise LegacyTypeGap('Modern top entry outside flat list')
        top.append(value)
    if position != len(plain):
        raise LegacyTypeGap('Trailing modern descriptor bytes')
    slice_bytes = blocks['DTHP']['payload']
    if len(slice_bytes) != 4:
        raise LegacyTypeGap('Unknown modern DTHP slice layout')
    slice_count, shift = struct.unpack('>2H', slice_bytes)
    if slice_count == 0 or shift == 0 or shift + slice_count - 1 > len(top):
        raise LegacyTypeGap('Modern DTHP slice outside top list')
    return dict(source_sha256=_sha(resaved_vi), saved_version_word='20008000',
        VCTP_resource_sha256=blocks['VCTP']['sha256'], VCTP_plain_sha256=_sha(plain),
        flat=flat, top_one_based=top, DTHP_count=slice_count, DTHP_index_shift=shift)


def corroborate_exact_port(original_vi, dco_offset, resaved_vi, resaved_bd_xml, correspondence):
    """Require explicit prior signature provenance and complete descriptor equality.

    This produces a metadata candidate receipt. It cannot turn multiset candidate
    correspondence into an original UID, whole-source, or native binding proof.
    """
    candidate = inspect_primitive_dco(original_vi, dco_offset)
    modern = read_resaved_types(resaved_vi)
    if type(resaved_bd_xml) is not bytes or len(resaved_bd_xml) > 1024 * 1024 or b'<!DOCTYPE' in resaved_bd_xml or b'<!ENTITY' in resaved_bd_xml:
        raise LegacyTypeGap('Unqualified corroborating XML input')
    if type(correspondence) is not dict or correspondence.get('strength') != 'G44_OPERATION_SLOT_OUTPUT_SIGNATURE_MULTISET_CANDIDATE':
        raise LegacyTypeGap('Missing qualified signature-candidate provenance')
    required = dict(original_source_sha256=candidate['original_source_sha256'],
        original_BDHP_sha256=candidate['BDHP_sha256'], resaved_source_sha256=modern['source_sha256'],
        resaved_BD_xml_sha256=_sha(resaved_bd_xml), primitive_chunk_offset=candidate['primitive_chunk_offset'],
        primitive_operation_id=candidate['primitive_operation_id'], parameter_index=candidate['parameter_index_byte50'],
        output_flag_projection=candidate['output_flag_projection'])
    if any(type(correspondence.get(k)) is not type(v) or correspondence[k] != v for k, v in required.items()):
        raise LegacyTypeGap('Correspondence source or selected-port identity disagreement')
    try:
        tree = ET.fromstring(resaved_bd_xml)
    except ET.ParseError as error:
        raise LegacyTypeGap('Malformed corroborating XML: ' + str(error))
    uid = correspondence.get('resaved_node_uid')
    term_uid = correspondence.get('resaved_terminal_uid')
    dco_uid = correspondence.get('resaved_dco_uid')
    if any(type(v) is not str or not v.isdigit() for v in (uid, term_uid, dco_uid)):
        raise LegacyTypeGap('Malformed selected resaved UID')
    nodes = [n for n in tree.iter() if n.get('class') and n.get('uid') == uid]
    if len(nodes) != 1 or nodes[0].get('class') != 'prim':
        raise LegacyTypeGap('Selected resaved primitive definition is missing or ambiguous')
    node = nodes[0]
    _selected_record(node, 'SL__arrayElement', 'prim')
    node_fields = {'objFlags', 'termList', 'bounds', 'shortCount', 'clumpNum', 'primResID', 'primIndex'}
    if any(child.tag not in node_fields for child in node):
        raise LegacyTypeGap('Unknown selected primitive field layout')
    for name in node_fields - {'termList'}:
        _scalar(node, name)
    if _scalar(node, 'primResID', required=True) != str(candidate['primitive_operation_id']):
        raise LegacyTypeGap('Selected resaved operation disagrees')
    counted_terms = _counted_terms(node, tree)
    if len(counted_terms) != len(candidate['original_counted_primitive_signature']):
        raise LegacyTypeGap('Original/resaved counted primitive membership disagrees')
    saved_signature = []
    for member in counted_terms:
        member_parameter = member.find('dco')
        member_index = _scalar(member_parameter, 'parmIndex')
        member_flags = _scalar(member_parameter, 'objFlags')
        saved_signature.append((_decimal(member_index, 'parmIndex') if member_index is not None else 0,
                                _decimal(member_flags, 'objFlags') & 1 if member_flags is not None else 0))
    original_signature = [(p['parameter_index'], p['output_flag_projection']) for p in candidate['original_counted_primitive_signature']]
    if sorted(saved_signature) != sorted(original_signature):
        raise LegacyTypeGap('Original/resaved complete counted primitive signature disagrees')
    terms = [t for t in counted_terms if t.get('uid') == term_uid]
    if len(terms) != 1:
        raise LegacyTypeGap('Selected resaved terminal is missing or ambiguous')
    if len([n for n in tree.iter() if n.get('class') and n.get('uid') == term_uid]) != 1:
        raise LegacyTypeGap('Duplicate selected resaved terminal definition')
    terminal = terms[0]
    dcos = terminal.findall('dco')
    if len(dcos) != 1 or dcos[0].get('class') != 'parm' or dcos[0].get('uid') != dco_uid:
        raise LegacyTypeGap('Selected resaved parameter definition disagrees')
    parameter = dcos[0]
    if len([n for n in tree.iter() if n.get('class') and n.get('uid') == dco_uid]) != 1:
        raise LegacyTypeGap('Duplicate selected resaved parameter definition')
    parameter_fields = {'objFlags', 'typeDesc', 'termBounds', 'primIndex', 'parmIndex'}
    if any(child.tag not in parameter_fields for child in parameter):
        raise LegacyTypeGap('Unknown selected parameter field layout')
    for name in parameter_fields:
        _scalar(parameter, name)
    node_index = _decimal(_scalar(node, 'primIndex', required=True), 'primitive.primIndex')
    parameter_index = _decimal(_scalar(parameter, 'primIndex', required=True), 'parameter.primIndex')
    if node_index != parameter_index:
        raise LegacyTypeGap('Selected resaved primitive/parameter index disagreement')
    index_text = _scalar(parameter, 'parmIndex')
    flags_text = _scalar(parameter, 'objFlags')
    # Absent zero projections remain explicitly inherited G44 metadata evidence.
    for text, value, field in ((index_text, candidate['parameter_index_byte50'], 'parmIndex'),
                               (flags_text, candidate['output_flag_projection'], 'objFlags')):
        if text is None:
            if value != 0:
                raise LegacyTypeGap('Absent resaved field contradicts inherited zero projection')
        else:
            parsed = _decimal(text, field)
            if (parsed if field == 'parmIndex' else parsed & 1) != value:
                raise LegacyTypeGap('Resaved parameter projection disagrees')
    type_fields = parameter.findall('typeDesc')
    if len(type_fields) != 1:
        raise LegacyTypeGap('Selected resaved type field is absent or repeated')
    match = re.match(r'^TypeID\(([1-9][0-9]*)\)\Z', _scalar(parameter, 'typeDesc', required=True))
    if match is None:
        raise LegacyTypeGap('Malformed selected resaved heap type expression')
    heap_id = int(match.group(1))
    if heap_id > modern['DTHP_count']:
        raise LegacyTypeGap('Selected resaved heap type exceeds slice')
    consolidated = modern['DTHP_index_shift'] + heap_id - 1
    flat = modern['flat'][modern['top_one_based'][consolidated - 1]]
    if candidate['descriptor']['descriptor_hex'] != flat['raw_hex']:
        raise LegacyTypeGap('Complete original/resaved descriptor bytes disagree')
    candidate.update(status='CORROBORATED_METADATA_CANDIDATE', exact_descriptor_bytes_equal=True,
        selected_one_based_schema_evidence=True, correspondence_strength=correspondence['strength'],
        correspondence_provenance=dict(correspondence), resaved_source_sha256=modern['source_sha256'],
        resaved_BD_xml_sha256=_sha(resaved_bd_xml), resaved_heap_type_id=heap_id,
        resaved_consolidated_one_based=consolidated, resaved_descriptor=flat,
        resaved_parmIndex_raw_state='ABSENT_G44_ZERO_PROJECTION' if index_text is None else 'PRESENT',
        resaved_objFlags_raw_state='ABSENT_G44_ZERO_PROJECTION' if flags_text is None else 'PRESENT',
        original_UID_correspondence_qualified=False, native_runtime_equivalence=False)
    return candidate
