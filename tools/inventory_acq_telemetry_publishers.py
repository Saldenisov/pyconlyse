"""Read-only lvkit XML census of all native Shared Variable publication sites.

Never writes a VI. UIDs identify the pinned export, not a portable NI API.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


def inventory(path):
    path = Path(path)
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    parents = {child: parent for parent in root.iter() for child in parent}
    objects = {node.get('uid'): node for node in root.iter() if node.get('class')}
    records = []
    for writer in root.iter():
        if writer.get('class') != 'sharedVariableDynamicWrite':
            continue
        diagram = parents[parents[writer]]
        if diagram.get('class') != 'diag':
            raise ValueError('publisher has no directly owning diagram')
        terminals = {term.findtext('dco/terminal_ID'): term for term in writer.findall('termList/*')}
        url_term, data_term = terminals['0B'], terminals['0A']
        url_wires = [wire for wire in diagram.findall('signalList/*')
                     if url_term.get('uid') in [t.get('uid') for t in wire.findall('termList/*')]]
        if len(url_wires) != 1:
            raise ValueError('publication URI wire is ambiguous')
        source = [t.get('uid') for t in url_wires[0].findall('termList/*')
                  if t.get('uid') != url_term.get('uid')]
        if len(source) != 1:
            raise ValueError('publication URI is not one direct constant')
        constant = objects[source[0]].findtext('dco/ConstValue')
        value = bytes.fromhex(constant)
        size = struct.unpack('!I', value[:4])[0]
        if size != len(value) - 4:
            raise ValueError('invalid native string constant length')
        uri = value[4:].decode('ascii')
        data_wires = [wire for wire in diagram.findall('signalList/*')
                      if data_term.get('uid') in [t.get('uid') for t in wire.findall('termList/*')]]
        if len(data_wires) != 1:
            raise ValueError('publication data wire is ambiguous')
        records.append(dict(writer_uid=writer.get('uid'), diagram_uid=diagram.get('uid'),
                            source_site='uid-' + writer.get('uid'), uri=uri,
                            publication=uri.rsplit('/', 1)[-1],
                            data_terminal_uid=data_term.get('uid'),
                            data_type=data_term.findtext('dco/typeDesc'),
                            data_wire_uid=data_wires[0].get('uid'),
                            native_hook_verified=False))
    return dict(export_sha256=hashlib.sha256(raw).hexdigest(),
                writer_count=len(records),
                publications=sorted({r['publication'] for r in records}),
                sites=records, instrumented_copy_complete=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xml')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = inventory(args.xml)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + '\n', encoding='utf-8')
    else:
        print(rendered)
