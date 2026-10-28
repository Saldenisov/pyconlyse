"""Decode binary LabVIEW DefaultData text without HTML or Unicode byte loss.

Input is parsed XML text with wrapping quotes. Numeric byte references are
decoded once; an escaped ampersand cannot start a second decoding pass.
Python 3.4-compatible standard-library APIs keep the decoder portable.
"""

import base64
import re
import zlib

_ENTITY = re.compile(r"&#(?:x([0-9A-Fa-f]+)|([0-9]+));")
_COMPRESSED_PREFIX = "lvkit-zlib:"


def decode_quoted_default_data(text, encoding="cp1252"):
    """Return exact flattened bytes from lvkit's quoted DefaultData text."""
    value = text.strip()
    if len(value) < 2 or value[0] != '"' or value[-1] != '"':
        raise ValueError("DefaultData requires one pair of wrapping quotes")
    value = value[1:-1]
    if value.startswith(_COMPRESSED_PREFIX):
        packed = value[len(_COMPRESSED_PREFIX) :].encode("ascii", "strict")
        return zlib.decompress(base64.b64decode(packed, validate=True))
    result = bytearray()
    offset = 0
    for match in _ENTITY.finditer(value):
        result.extend(value[offset : match.start()].encode(encoding, "strict"))
        number = (
            int(match.group(1), 16)
            if match.group(1) is not None
            else int(match.group(2), 10)
        )
        if not 0 <= number <= 255:
            raise ValueError("DefaultData entity exceeds one byte")
        result.append(number)
        offset = match.end()
    result.extend(value[offset:].encode(encoding, "strict"))
    return bytes(result)


def install_default_data_inverse():
    """Patch only pylabview's DefaultData tag in the current process.

    Display strings and [NULL] retain the original decoder. pylabview is an
    optional dependency: the pure decoder above does not import it.
    """
    # pylabview needs datatype initialization before direct LVheap import.
    from pylabview import (
        LVdatatype,  # noqa: F401
        LVheap,
    )

    previous = LVheap.HeapNodeString.initContentWithXML
    if getattr(previous, "_native_default_data_exact_inverse", False):
        return
    default_tag = LVheap.OBJ_FIELD_TAGS.OF__DefaultData

    def inverse(self, text):
        if self.tagEn != default_tag or text == "[NULL]":
            return previous(self, text)
        self.content = decode_quoted_default_data(text, self.vi.textEncoding)

    inverse._native_default_data_exact_inverse = True
    inverse.__wrapped__ = previous
    LVheap.HeapNodeString.initContentWithXML = inverse
