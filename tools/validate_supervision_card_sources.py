"""Read-only source/hash/wire validation for SuperVision card profiles."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import re
import xml.etree.ElementTree as ET

from legacy.xp_acq_control.elyse_agent.synchronization_profiles import (
    SUPERVISION_INIT_SHA256, SUPERVISION_INIT_XML_SHA256,
    SUPERVISION_ROOT_SHA256, SUPERVISION_ROOT_XML_SHA256,
    SUPERVISION_FRAMES, SUPERVISION_CHANNEL_NODES, SUPERVISION_START_NODES,
    supervision_counter_profile,
)
from legacy.xp_acq_control.elyse_agent.supervision_imaq import source_video_configuration


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def load_receipt(folder, name, vi_sha, xml_sha):
    receipt = json.loads((folder / name).read_text())
    assert receipt['sha256'] == vi_sha
    assert sha(receipt['source']) == vi_sha
    assert receipt['xml'][0]['sha256'] == xml_sha
    assert sha(receipt['xml'][0]['path']) == xml_sha
    return receipt, ET.parse(receipt['xml'][0]['path']).getroot()


def nodes(root):
    return {node.get('uid'): node for node in root.iter() if node.get('class') is not None}


def nets(diagram):
    return [frozenset(t.get('uid') for t in s.findall('termList/*'))
            for s in diagram.find('signalList')]


def wired_constant(root_nodes, diagram, term):
    connected = set().union(*(s for s in nets(diagram) if term in s)) - {term}
    values = [root_nodes[uid].findtext('dco/ConstValue') for uid in connected if uid in root_nodes]
    values = [value for value in values if value is not None]
    assert len(values) == 1, (term, connected, values)
    return values[0]


def parameter(node, index):
    return next(t.get('uid') for t in node.findall('termList/*')
                if int(t.findtext('dco/paramIdx', '0')) == index)


def lv_string(raw):
    data = bytes.fromhex(raw)
    assert len(data) == 4 + int.from_bytes(data[:4], 'big')
    return data[4:].decode('ascii')


def validate(folder):
    folder = Path(folder)
    unused, init = load_receipt(folder, '01.json', SUPERVISION_INIT_SHA256, SUPERVISION_INIT_XML_SHA256)
    by = nodes(init)
    for i, row in enumerate(supervision_counter_profile()):
        diagram, node = by[SUPERVISION_FRAMES[i]], by[SUPERVISION_CHANNEL_NODES[i]]
        assert node.findtext('label/textRec/text') == '"DAQmx Create Virtual Channel.vi"'
        assert int(wired_constant(by, diagram, parameter(node, 1)), 16) == row['high_ticks']
        assert int(wired_constant(by, diagram, parameter(node, 2)), 16) == row['low_ticks']
        assert lv_string(wired_constant(by, diagram, parameter(node, 5))) == row['physical_channel']
        assert lv_string(wired_constant(by, diagram, parameter(node, 9))) == row['timebase']
        assert int(wired_constant(by, diagram, parameter(node, 12)), 16) == 0x27e6
        assert int(wired_constant(by, diagram, parameter(node, 13)), 16) == 0
        start = by[SUPERVISION_START_NODES[i]]
        assert start.findtext('label/textRec/text') == '"DAQmx Start Task.vi"'
        assert start in list(diagram.find('zPlaneList'))
        trigger = next(n for n in diagram.find('zPlaneList')
            if n.get('class') == 'polyIUse' and n.findtext('label/textRec/text') == '"DAQmx Trigger.vi"')
        assert lv_string(wired_constant(by, diagram, parameter(trigger, 5))) == row['trigger']
        assert int(wired_constant(by, diagram, parameter(trigger, 7)), 16) == 0x2828
        properties = {int(term.findtext('dco/propList/*/PropItemCode')): term.get('uid')
            for n in diagram.find('zPlaneList') if n.get('class') == 'propNode'
            for term in n.findall('termList/*') if term.findtext('dco/propList/*/PropItemCode') is not None}
        assert set(properties) == {6415, 4464, 833}
        for code, literal in ((6415, 1), (4464, 0x27e6), (833, 0x2828)):
            assert int(wired_constant(by, diagram, properties[code]), 16) == literal
        timing = next(n for n in diagram.find('zPlaneList')
            if n.get('class') == 'polyIUse' and n.findtext('label/textRec/text') == '"DAQmx Timing.vi"')
        assert int(wired_constant(by, diagram, parameter(timing, 1)), 16) == 0x27c2
        assert int(wired_constant(by, diagram, parameter(timing, 2)), 16) == 1
    receipt, root = load_receipt(folder, '00.json', SUPERVISION_ROOT_SHA256, SUPERVISION_ROOT_XML_SHA256)
    by = nodes(root)
    assert by['18953'].findtext('label/textRec/text') == '"IMAQ Init.vi"'
    assert by['18912'].findtext('label/textRec/text') == '"IMAQ Grab Setup.vi"'
    assert by['15740'].findtext('label/textRec/text') == '"IMAQ Grab Acquire.vi"'
    assert lv_string(by['18857'].findtext('dco/ConstValue')) == 'img0'
    properties = {n.findtext('PropItemName'): int(n.findtext('PropItemCode'))
                  for n in by['15292'].iter() if n.get('class') == 'propItemInfo'}
    assert properties['"White Reference"'] == 0x3ff600bd
    assert properties['"Black Reference"'] == 0x3ff600bc
    camera_nets = nets(by['12058'])
    for endpoints in (("18857", "18989"), ("18965", "15321"),
                      ("15344", "18950"), ("51294", "18931")):
        assert any(set(endpoints) <= wire for wire in camera_nets), endpoints
    fp = receipt['xml'][1]
    assert sha(fp['path']) == fp['sha256']
    front = nodes(ET.parse(fp['path']).getroot())
    def default(uid):
        text = front[uid].findtext('DefaultData').replace('&amp;', '&')
        # These entities encode binary data, not HTML text: HTML decoding
        # would change NUL/control bytes and CP1252 numeric references.
        text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)
        return text[1:-1].encode('latin1')
    actual = dict(channel=int.from_bytes(default('19558'), 'big'),
                  white_ref_volt=struct.unpack('>d', default('15301'))[0],
                  black_ref_volt=struct.unpack('>d', default('19202'))[0])
    assert actual == source_video_configuration(), actual
    return dict(counter_frames=8, counter_initialization_verified=True,
                video_interface='img0', video_saved_defaults=actual,
                source_hashes_verified=True, hardware_executed=False,
                physical_timebase_verified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt_directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.receipt_directory), sort_keys=True))
