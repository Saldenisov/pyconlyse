"""Lossless bounded version-P framing and code7 reference-table decoding.

Only record boundaries and reference targets are interpreted. Remaining data,
header flags, record word1, class layouts and runtime behavior stay opaque.
This does not produce an executable VI or invent original object UIDs.
"""
import hashlib
import struct
import binascii


class PointerHeapGap(ValueError):
    pass


def _take(raw, offset, size):
    if offset < 0 or size < 0 or offset+size > len(raw):
        raise PointerHeapGap('Truncated pointer heap field')
    return raw[offset:offset+size]


def _u32(raw, offset):
    return struct.unpack('>I', _take(raw, offset, 4))[0]


def _sha(raw):
    return hashlib.sha256(raw).hexdigest().upper()


def _hex(raw):
    return binascii.hexlify(raw).decode('ascii').upper()


def decode_pointer_heap(raw):
    if type(raw) is not bytes or not 76 <= len(raw) <= 64*1024*1024 or len(raw)%4:
        raise PointerHeapGap('Unqualified pointer heap size')
    magic=raw[4:8]
    if magic not in (b'BDHP', b'FPHP'):
        raise PointerHeapGap('Unqualified pointer heap magic')
    if _u32(raw,8)!=68 or _u32(raw,16)!=56:
        raise PointerHeapGap('Unqualified pointer heap header profile')
    end=len(raw)-8
    if _u32(raw,20)!=end or _u32(raw,32)!=len(raw)-1:
        raise PointerHeapGap('Pointer heap length fields disagree')
    if raw[end:]!=b'\x00\x00\x00\x09\x00\x00\x00\x00':
        raise PointerHeapGap('Unqualified pointer heap footer')
    records=[];pos=56
    while pos<end:
        word=_u32(raw,pos);size=word&~3;flags=word&3
        if flags not in (0,1) or size<12 or size>end-pos:
            raise PointerHeapGap('Invalid pointer heap chunk at '+str(pos))
        part=_take(raw,pos,size)
        records.append(dict(offset=pos,bytes=size,chunk_word=word,low_flags=flags,
            word1=_u32(part,4),type_code=_u32(part,8) if not flags else None,
            raw=part,sha256=_sha(part),reference_table=None))
        pos+=size
    if pos!=end:
        raise PointerHeapGap('Pointer heap partition does not consume body')
    targets={r['offset']+12:r for r in records if r['low_flags']==0}
    for record in records:
        if record['low_flags'] or record['type_code']!=7:
            continue
        part=record['raw'];count=_u32(part,12)
        if count>(len(part)-16)//4:
            raise PointerHeapGap('Code7 count exceeds record storage')
        values=[_u32(part,16+4*i) for i in range(count)]
        links=[]
        for index,value in enumerate(values):
            if value and value not in targets:
                raise PointerHeapGap('Code7 reference is not an observed record-data boundary')
            target=targets.get(value)
            links.append(dict(index=index,raw_value=value,
                target_offset=target['offset'] if target else None,
                target_type_code=target['type_code'] if target else None))
        record['reference_table']=dict(count=count,links=links,
            opaque_tail_hex=_hex(part[16+4*count:]))
    return dict(magic=magic.decode('ascii'),bytes=len(raw),sha256=_sha(raw),
        header=raw[:56],footer=raw[end:],records=records,
        original_UIDs_qualified=False,business_body_decoded=False)


def encode_pointer_heap(model):
    raw=model['header']+b''.join(r['raw'] for r in model['records'])+model['footer']
    checked=decode_pointer_heap(raw)
    if checked['sha256']!=model['sha256'] or checked['bytes']!=model['bytes']:
        raise PointerHeapGap('Pointer heap model does not retain source bytes')
    return raw


def compact_pointer_heap(model):
    return dict(magic=model['magic'],bytes=model['bytes'],sha256=model['sha256'],
        header_hex=_hex(model['header']),footer_hex=_hex(model['footer']),
        records=[{k:v for k,v in r.items() if k!='raw'} for r in model['records']],
        original_UIDs_qualified=False,business_body_decoded=False)
