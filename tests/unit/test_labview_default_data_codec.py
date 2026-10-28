"""Exact DefaultData byte regressions for CPython 3.4 and 3.12."""

import base64
import sys
import unittest
import xml.etree.ElementTree as ET
import zlib
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from tools.labview_default_data_codec import (
    decode_quoted_default_data,
    install_default_data_inverse,
)


def encoded(value):
    return '"' + "".join("&#x{:02x};".format(b) for b in value) + '"'


class LabviewDefaultDataCodecTests(unittest.TestCase):
    def test_all256_bytes_through_xml_export_parse(self):
        value = bytes(bytearray(range(256)))
        node = ET.Element("DefaultData")
        node.text = encoded(value)
        parsed = ET.fromstring(ET.tostring(node, encoding="utf-8"))
        self.assertEqual(decode_quoted_default_data(parsed.text), value)

    def test_c1_bytes_keep_their_byte_values(self):
        self.assertEqual(
            decode_quoted_default_data('"&#x80;&#x81;&#x8d;&#x9f;&#xff;"'),
            bytes.fromhex("80818d9fff"),
        )

    def test_literal_numeric_looking_payload_is_not_decoded_twice(self):
        self.assertEqual(decode_quoted_default_data('"&#x26;#x80;"'), b"&#x80;")
        for value in (b"&#x80;", b"&#128;", b"&amp;#x80;", b"&#x00;"):
            self.assertEqual(decode_quoted_default_data(encoded(value)), value)

    def test_named_xml_entities_belong_to_the_xml_layer(self):
        for value in (b"&<>\"'", b"&amp;#x80;", b"&lt;&gt;&quot;&apos;"):
            node = ET.Element("DefaultData")
            node.text = encoded(value)
            parsed = ET.fromstring(ET.tostring(node, encoding="utf-8"))
            self.assertEqual(decode_quoted_default_data(parsed.text), value)

    def test_original_eight_byte_double_stays_eight_bytes(self):
        value = bytes.fromhex("3ec0c6f7a0b5ed8d")
        self.assertEqual(decode_quoted_default_data(encoded(value)), value)
        self.assertEqual(len(decode_quoted_default_data(encoded(value))), 8)

    def test_decimal_entities_and_already_parsed_control_bytes(self):
        self.assertEqual(
            decode_quoted_default_data('"&#128;&#255;\x00"'), b"\x80\xff\x00"
        )

    def test_literal_spans_use_the_requested_codec_strictly(self):
        self.assertEqual(decode_quoted_default_data('"\u00e9\u20ac"'), b"\xe9\x80")
        with self.assertRaises(UnicodeEncodeError):
            decode_quoted_default_data('"\u4e2d"')

    def test_outer_whitespace_preserves_inner_spaces(self):
        self.assertEqual(decode_quoted_default_data(' \n "  a b  " \n'), b"  a b  ")

    def test_compressed_defaults_and_reserved_prefix_payload(self):
        for value in (b"\x00" * 70000, b"lvkit-zlib:literal original bytes"):
            packed = base64.b64encode(zlib.compress(value)).decode("ascii")
            self.assertEqual(
                decode_quoted_default_data('"lvkit-zlib:' + packed + '"'), value
            )

    def test_invalid_compressed_text_rejects(self):
        with self.assertRaises(ValueError):
            decode_quoted_default_data('"lvkit-zlib:%%%"')

    def test_out_of_range_entities_reject(self):
        for value in ('"&#x100;"', '"&#256;"'):
            with self.assertRaisesRegex(ValueError, "one byte"):
                decode_quoted_default_data(value)

    def test_quoted_contract_rejects_unquoted_values(self):
        with self.assertRaisesRegex(ValueError, "wrapping quotes"):
            decode_quoted_default_data("not quoted")

    def test_pylabview_installer_is_optional_scoped_and_idempotent(self):
        default_tag, display_tag = object(), object()

        class HeapString(object):
            def initContentWithXML(self, text):
                self.content = (
                    False if text == "[NULL]" else text[1:-1].encode("cp1252")
                )

        heap = SimpleNamespace(
            HeapNodeString=HeapString,
            OBJ_FIELD_TAGS=SimpleNamespace(OF__DefaultData=default_tag),
        )
        package = ModuleType("pylabview")
        package.LVdatatype = ModuleType("pylabview.LVdatatype")
        package.LVheap = heap
        with patch.dict(sys.modules, {"pylabview": package}):
            install_default_data_inverse()
            method = HeapString.initContentWithXML
            install_default_data_inverse()
            self.assertIs(method, HeapString.initContentWithXML)
            node = HeapString()
            node.tagEn, node.vi = default_tag, SimpleNamespace(textEncoding="cp1252")
            node.initContentWithXML('"&#x80;"')
            self.assertEqual(node.content, b"\x80")
            node.initContentWithXML("[NULL]")
            self.assertIs(node.content, False)
            node.initContentWithXML('""')
            self.assertEqual(node.content, b"")
            node.tagEn = display_tag
            node.initContentWithXML('"&#x80;"')
            self.assertEqual(node.content, b"&#x80;")


if __name__ == "__main__":
    unittest.main()
