"""Conditional APP-30 whole-output projection, not native VI equivalence.

The original has two nMux nodes and two constants. Every Bundle271 field
is wired, eliminating its prototype172 values from final output. Literal303
and absent String-field indices remain explicit caller hypotheses. Size
outside the shared U16/I16 positive range is refused. Bytes are an opaque
String carrier: no encoding, native serializer or native execution is implied.
"""
from collections import namedtuple

GraphicsFont = namedtuple('GraphicsFont', 'font_name size strikeout italic underline outline shadow bold')
SOURCE_ID = 'APP-30'
SOURCE_VERSION = '9BDFAD61853E53EE0F7475768F9D927EBD648BDC425EFE4187925707AD5A9F76'


def _integer(value, lower, upper, name):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(name + ': exact integer outside admitted domain')
    return value


def convert_property_node_font_to_graphics_font(font, *, decoded_constant_303, field_index_bindings):
    """Return all eight fields conditional on supplied unresolved source facts.

    font: tuple/list (opaque Name bytes, Size, Bold, Italic, Underline,
    Strikeout, Color). Size is 0..32767; Color is U32. Four flags are exact
    bool. decoded_constant_303 is exact bool supplied for raw DCO301
    DefaultData0000; neither bool is claimed to be its original decoding.
    field_index_bindings must explicitly give {'247':0,'277':0}. These
    candidate paths match unique String descriptors; original i is absent.
    """
    if type(font) not in (tuple, list) or len(font) != 7:
        raise ValueError('font: exact seven-field positional carrier required')
    name, size, bold, italic, underline, strikeout, color = font
    if type(name) is not bytes or len(name) > 4096:
        raise ValueError('FontName: opaque bytes limited to4096')
    _integer(size, 0, 32767, 'SizeU16I16SharedDomain')
    _integer(color, 0, 4294967295, 'ColorU32')
    if any(type(v) is not bool for v in (bold, italic, underline, strikeout)):
        raise ValueError('font: four exact Boolean carriers required')
    if type(decoded_constant_303) is not bool:
        raise ValueError('decoded_constant_303: explicit exact Boolean hypothesis required')
    if type(field_index_bindings) is not dict or set(field_index_bindings) != {'247','277'}:
        raise ValueError('field_index_bindings: both absent-i String candidates required')
    for uid in ('247','277'):
        _integer(field_index_bindings[uid], 0, 0, 'field_index_bindings.' + uid)
    # Wire335 Name;332 Size;320 Strikeout;327 Italic;323 Underline;
    # star317 (303->294,291) Shadow+Outline;330 Bold. Seed172 is fully overwritten.
    return GraphicsFont(name, size, strikeout, italic, underline,
        decoded_constant_303, decoded_constant_303, bold)
