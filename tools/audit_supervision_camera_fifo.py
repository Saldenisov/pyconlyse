"""Read-only graph audit of the native SuperVision FIFO preparation.

Requires lvkit/pylabview for extraction. Writes XML/JSON, never a VI. Native
LabVIEW saves and SaveForPrevious exports are the only binary writers used.
The audit does not execute LabVIEW, NI, sockets, or an XP deployment.
"""

import argparse
from collections import Counter
import contextlib
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


PACKAGE = Path('legacy/labview/supervision_telemetry/realtime_fifo_20261029')
BASE = Path('legacy/labview/supervision_telemetry/individual_helpers')
FILES = {
    'tap': (BASE / 'camera/SUP_Camera_FrameTap.vi', PACKAGE / 'camera/SUP_Camera_FrameTap.vi'),
    'producer': (BASE / 'camera/observer_v3/SUP_Camera_Queue_Latest.vi', PACKAGE / 'camera/observer_v3/SUP_Camera_Queue_Latest.vi'),
    'consumer': (BASE / 'camera/SUP_Camera_Transport.vi', PACKAGE / 'camera/SUP_Camera_Transport.vi'),
    'entry': (PACKAGE / 'baseline/entry_stopped.vi', PACKAGE / 'entry/START_Supervision_Telemetry_Camera_FIFO.vi'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_graph(path, out):
    from lvkit import extractor
    out.mkdir(parents=True, exist_ok=False)
    with (out / 'extract.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        bd, fp, metadata = extractor.extract_vi_xml(path, out / 'xml')
    return Graph(ET.parse(bd).getroot(), ET.parse(fp).getroot(), ET.parse(metadata).getroot())


class Graph:
    def __init__(self, bd, fp, meta):
        self.bd, self.fp, self.meta = bd, fp, meta
        self.nodes = {n.get('uid'): n for n in bd.iter() if n.get('uid') and n.get('class')}
        self.constants = {u: n.findtext('ConstValue') for u, n in self.nodes.items() if n.get('class') == 'bDConstDCO'}
        self.primitives = {u: n.findtext('primResID') for u, n in self.nodes.items() if n.get('class') == 'prim'}
        self.wires = []
        for n in bd.iter():
            if n.get('class') == 'signal':
                terms = [t.get('uid') for t in n.find('termList')]
                assert len(terms) >= 2, ('dangling wire', n.get('uid'))
                self.wires.append((terms[0], tuple(sorted(terms[1:]))))

    def port(self, uid, param):
        matches = [t.get('uid') for t in self.nodes[uid].find('termList')
                   if int(t.findtext('dco/parmIndex', '0')) == param]
        assert len(matches) == 1, (uid, param, matches)
        return matches[0]

    def has_wire(self, source, sink):
        return any(a == source and sink in bs for a, bs in self.wires)

    def constant_term(self, uid):
        matches = [n.get('uid') for n in self.bd.iter() if n.get('class') == 'term'
                   and n.find('dco') is not None and n.find('dco').get('uid') == uid]
        assert len(matches) == 1, (uid, matches)
        return matches[0]

    def calls(self):
        result = []
        for link in self.meta.findall('LIbd/Section/BDHP/*'):
            name = [s.text or '' for s in link.findall('LinkSaveQualName/String')]
            if not name:
                continue
            result.append((tuple(name), tuple(s.text or '' for s in link.findall('LinkSavePathRef/String')),
                           tuple(s.text for s in link.findall('LinkOffsetList/Offset'))))
        return sorted(result)

    def abi(self):
        result = []
        for n in self.fp.iter():
            if n.get('class') != 'fPDCO':
                continue
            labels = [x.findtext('textRec/text') for x in n.findall('ddo/partsList/SL__arrayElement')
                      if x.get('class') == 'label' and x.findtext('partID') == '16']
            result.append((n.get('uid'), n.findtext('conNum', '0'), int(n.findtext('objFlags', '0')) & 1,
                           n.find('ddo').get('class'), tuple(labels)))
        return sorted(result)

    def structure(self):
        # Containment and original node identities; excludes compiler type IDs,
        # primitive-table indices, screen geometry and wire routing geometry.
        ignored = {'signal', 'label', 'parm', 'term', 'bDConstDCO', 'prim'}
        return sorted((u, n.get('class')) for u, n in self.nodes.items() if n.get('class') not in ignored)

    def execution_flags(self):
        return dict(self.meta.find('LVSR/Section/Execution').attrib)


def audit_pair(name, before, after):
    assert before.calls() == after.calls(), (name, 'callee links changed')
    assert before.abi() == after.abi(), (name, 'front-panel/connector contract changed')
    assert before.structure() == after.structure(), (name, 'structure/node identities changed')
    changed = {u: [before.constants.get(u), after.constants.get(u)]
               for u in set(before.constants) | set(after.constants)
               if before.constants.get(u) != after.constants.get(u)}
    expected = {
        'tap': {'988': ['000003E8', '0000000000']},
        'producer': {'90': ['00000001', '00000080']},
        'consumer': {'1099': ['00000001', '00000080']},
        'entry': {'2404': ['00000001', '00000080']},
    }[name]
    assert changed == expected, (name, 'unexpected constant changes', changed)
    if name != 'producer':
        assert before.primitives == after.primitives, (name, 'primitive operations changed')
        assert Counter(before.wires) == Counter(after.wires), (name, 'signal topology changed')
    else:
        assert before.primitives == {'222': '9130', '529': '1062', '112': '9109', '43': '9108'}
        assert after.primitives == {'192': '9111', '529': '1062', '112': '9109', '43': '9108'}
        mapping = dict(zip(['227', '230', '239', '248', '257', '260'],
                           ['208', '211', '218', '221', '226', '232']))
        expected_wires = [(mapping.get(a, a), tuple(sorted(mapping.get(b, b) for b in bs)))
                          for a, bs in before.wires]
        expected_wires.append((after.constant_term('299'), (after.port('192', 2),)))
        assert Counter(expected_wires) == Counter(after.wires), ('producer', 'unexpected signal topology')
        assert after.has_wire(after.port('43', 8), after.port('192', 0))
        assert after.has_wire(after.port('192', 8), after.port('112', 0))
        assert after.has_wire(after.port('192', 11), after.port('112', 3))
        assert after.has_wire(after.port('192', 10), after.port('529', 2))
        assert after.constants['299'] == '0000000000'
        assert after.constants['158'] == '0000'  # producer cannot create a queue
    flags = after.execution_flags()
    assert flags['RunOnOpen'] == '0'
    assert all(flags[k] == '0' for k in ('BadSignal', 'BadCompile', 'CompilerBug', 'HasInsaneItems'))
    # The entry was intentionally edited without loading hardware callees.
    # Its unresolved nodes must be rebound/compiled in the complete XP closure.
    assert flags['BadNode'] == ('1' if name == 'entry' else '0')
    return {'constant_changes': changed, 'primitive_count': len(after.primitives),
            'wire_count': len(after.wires), 'callee_links_unchanged': True,
            'fp_connector_contract_unchanged': True, 'structure_unchanged': True,
            'source_graph_checked': True, 'saved_execution_flags': flags,
            'native12_complete_dependency_load_pending': name == 'entry'}


def audit(repo, output):
    result = {'kind': 'NATIVE_CAMERA_FIFO_READ_ONLY_AUDIT', 'Run': False,
              'RSRC_writer': False, 'xp_deployed': False, 'runtime_25Hz_qualified': False, 'files': {}}
    for name, (original, candidate) in FILES.items():
        original, candidate = repo / original, repo / candidate
        hashes = (sha(original), sha(candidate))
        before = read_graph(original, output / (name + '_before'))
        after = read_graph(candidate, output / (name + '_after'))
        checks = audit_pair(name, before, after)
        assert hashes == (sha(original), sha(candidate)), 'audit modified VI bytes'
        checks.update({'before_sha256': hashes[0], 'after_sha256': hashes[1],
                       'candidate': str(candidate.relative_to(repo)).replace('\\', '/')})
        result['files'][name] = checks
    result['passed'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.repo, args.output)
    with (args.output / 'source_audit.json').open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
