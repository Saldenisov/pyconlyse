"""Malformed framing and lossless inactive storage tests; no native operation."""
import struct
import unittest
from tools.decode_labview_pointer_heap import (
    PointerHeapGap, compact_pointer_heap, decode_pointer_heap, encode_pointer_heap,
)


def fixture():
    # Code7 list at56 points to data address92 of code47 record at80.
    body=struct.pack('>6I',24,45,7,1,92,0xABCDEF01)+struct.pack('>4I',16,45,47,0)
    raw=bytearray(56+len(body)+8)
    raw[4:8]=b'BDHP'
    for offset,value in ((8,68),(16,56),(20,len(raw)-8),(24,56),(32,len(raw)-1)):
        struct.pack_into('>I',raw,offset,value)
    raw[56:56+len(body)]=body
    raw[-8:]=struct.pack('>2I',9,0)
    return bytes(raw)


class PointerHeapTests(unittest.TestCase):
    def test_roundtrip_and_exact_target(self):
        raw=fixture();model=decode_pointer_heap(raw)
        self.assertEqual(encode_pointer_heap(model),raw)
        self.assertEqual(model['records'][0]['reference_table']['links'][0]['target_offset'],80)
        self.assertEqual(model['records'][0]['reference_table']['opaque_tail_hex'],'ABCDEF01')
        self.assertFalse(compact_pointer_heap(model)['original_UIDs_qualified'])

    def test_every_truncated_prefix(self):
        raw=fixture()
        for end in range(len(raw)):
            with self.assertRaises(PointerHeapGap):decode_pointer_heap(raw[:end])

    def test_consistent_model_mutation_is_not_silent(self):
        model=decode_pointer_heap(fixture());model['records'][1]['raw']=b'\x00'*16
        with self.assertRaises(PointerHeapGap):encode_pointer_heap(model)

    def test_low_flag_is_separate_from_size(self):
        raw=bytearray(fixture());struct.pack_into('>I',raw,80,17)
        with self.assertRaises(PointerHeapGap):decode_pointer_heap(bytes(raw))
        struct.pack_into('>I',raw,72,0)
        model=decode_pointer_heap(bytes(raw))
        self.assertEqual(model['records'][1]['low_flags'],1)
        self.assertEqual(model['records'][1]['bytes'],16)
        self.assertEqual(encode_pointer_heap(model),bytes(raw))

    def test_bad_count_and_non_boundary_reference(self):
        for offset,value in ((68,1000),(72,91),(72,80),(56,26)):
            raw=bytearray(fixture());struct.pack_into('>I',raw,offset,value)
            with self.assertRaises(PointerHeapGap):decode_pointer_heap(bytes(raw))

    def test_null_and_empty_tables_preserve_tail(self):
        raw=bytearray(fixture());struct.pack_into('>I',raw,72,0)
        model=decode_pointer_heap(bytes(raw))
        self.assertIsNone(model['records'][0]['reference_table']['links'][0]['target_offset'])
        struct.pack_into('>I',raw,68,0)
        model=decode_pointer_heap(bytes(raw))
        self.assertEqual(model['records'][0]['reference_table']['opaque_tail_hex'],'00000000ABCDEF01')


if __name__=='__main__':unittest.main()
