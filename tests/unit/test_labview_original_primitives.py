"""Primitive references require exact owner,class,index and shape."""
import struct
import unittest
from tools.decode_labview_original_primitives import decode_original_primitives, PointerHeapGap


def fixture():
    # Chunks:prim56,list108,term128,parameter160.
    primitive=bytearray(52);struct.pack_into('>3I',primitive,0,52,45,47)
    struct.pack_into('>I',primitive,20,120);struct.pack_into('>2H',primitive,48,1420,189)
    table=struct.pack('>5I',20,45,7,1,140)
    term=struct.pack('>8I',32,45,21,0,68,0,172,140)
    parm=bytearray(52);struct.pack_into('>3I',parm,0,52,45,48)
    struct.pack_into('>2I',parm,12,257,68);struct.pack_into('>H',parm,48,189)
    parm[50]=3;parm[51]=2
    raw=bytearray(56)+primitive+table+term+parm+struct.pack('>2I',9,0)
    raw[4:8]=b'BDHP'
    for offset,value in ((8,68),(16,56),(20,len(raw)-8),(32,len(raw)-1)):
        struct.pack_into('>I',raw,offset,value)
    return bytes(raw)


class PrimitiveTests(unittest.TestCase):
    def test_slot_byte_and_opaque_trailing_byte(self):
        node=decode_original_primitives(fixture())['nodes'][0]
        self.assertEqual((node['prim_res_id'],node['original_prim_index']),(1420,189))
        port=node['ports'][0]
        self.assertEqual(port['parameter_index'],3)
        self.assertEqual(port['opaque_byte51'],2)
        self.assertEqual(port['output_flag_projection'],1)
        self.assertEqual(port['raw_dco_flags'],257)
        self.assertIsNone(node['original_UID'])

    def test_owner_index_and_target_disagreement(self):
        for offset,value,fmt in ((144,0,'>I'),(176,0,'>I'),(208,194,'>H'),(152,140,'>I'),(76,140,'>I')):
            raw=bytearray(fixture());struct.pack_into(fmt,raw,offset,value)
            with self.assertRaises(PointerHeapGap):decode_original_primitives(bytes(raw))

    def test_extra_opaque_type_word_not_coerced(self):
        raw=bytearray(fixture());struct.pack_into('>I',raw,180,0xDEADBEEF)
        port=decode_original_primitives(bytes(raw))['nodes'][0]['ports'][0]
        self.assertEqual(port['opaque_type_descriptor_word'],0xDEADBEEF)
        self.assertFalse(port['types_qualified'])


if __name__=='__main__':unittest.main()
