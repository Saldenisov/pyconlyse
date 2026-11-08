"""Bounded original code47/code21/code48 field projection.

Fields are qualified against independently hashed resaved XML signatures.
Type-description words and trailing byte51 remain opaque;no original UID,
native behavior,coercion or wire routing is inferred.
"""
import struct
from tools.decode_labview_pointer_heap import decode_pointer_heap, PointerHeapGap


def _word(raw,offset):
    if offset<0 or offset+4>len(raw):raise PointerHeapGap('Truncated primitive field')
    return struct.unpack_from('>I',raw,offset)[0]


def decode_original_primitives(raw):
    heap=decode_pointer_heap(raw)
    bydata={r['offset']+12:r for r in heap['records'] if r['low_flags']==0}
    def target(value,code):
        result=bydata.get(value)
        if result is None or result['type_code']!=code:
            raise PointerHeapGap('Original primitive reference has wrong target class')
        return result
    nodes=[]
    for record in heap['records']:
        if record['low_flags'] or record['type_code']!=47:continue
        if record['bytes']!=52:raise PointerHeapGap('Unqualified original primitive shape')
        offset=record['offset'];prim_id,prim_index=struct.unpack_from('>2H',raw,offset+48)
        table=target(_word(raw,offset+20),7)
        ports=[]
        for link in table['reference_table']['links']:
            if not link['raw_value']:raise PointerHeapGap('Null primitive terminal outside qualified scope')
            term=target(link['raw_value'],21)
            if term['bytes']!=32:raise PointerHeapGap('Unqualified original terminal shape')
            t=term['offset'];dco=target(_word(raw,t+24),48)
            if dco['bytes']!=52:raise PointerHeapGap('Unqualified original parameter shape')
            d=dco['offset']
            if _word(raw,t+16)!=offset+12 or _word(raw,d+16)!=offset+12:
                raise PointerHeapGap('Original primitive port owner disagreement')
            dco_index=struct.unpack_from('>H',raw,d+48)[0]
            if dco_index!=prim_index:raise PointerHeapGap('Original primitive index disagreement')
            flags=_word(raw,d+12)
            ports.append(dict(list_index=link['index'],terminal_offset=t,dco_offset=d,
                parameter_index=raw[d+50],output_flag_projection=flags&1,
                original_prim_index=dco_index,raw_dco_flags=flags,raw_terminal_flags=_word(raw,t+12),
                opaque_type_descriptor_word=_word(raw,d+20),opaque_byte51=raw[d+51],
                raw_terminal_word20=_word(raw,t+20),raw_terminal_word28=_word(raw,t+28),
                terminal_sha256=term['sha256'],dco_sha256=dco['sha256'],
                types_qualified=False,wire_routing_qualified=False))
        if len({p['parameter_index'] for p in ports})!=len(ports):
            raise PointerHeapGap('Repeated original parameter index')
        nodes.append(dict(offset=offset,prim_res_id=prim_id,original_prim_index=prim_index,
            term_list_offset=table['offset'],ports=ports,source_chunk_sha256=record['sha256'],
            original_UID=None,native_runtime_equivalence=False))
    return dict(heap_sha256=heap['sha256'],nodes=nodes,original_UIDs_qualified=False,
                business_body_decoded=False)
