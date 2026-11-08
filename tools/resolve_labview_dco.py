"""Resolve saved nMux aggregate DCO references; no inferred runtime types.

The input terminal may contain only <dco uid=.../>. Its aggregate type is
stored on the output terminal's nmxDCO definition. All links are checked;
missing or ambiguous definitions remain explicit refusals.
"""
import xml.etree.ElementTree as ET

def resolve_nmx_aggregate(root,terminal_uid):
    if type(terminal_uid) is not str:
        raise ValueError('terminal UID must be string')
    terms=[e for e in root.iter() if e.get('class')=='term' and e.get('uid')==terminal_uid]
    if len(terms)!=1:
        raise ValueError('unique full terminal definition required')
    term=terms[0]
    parents={child:parent for parent in root.iter() for child in parent}
    owner=parents.get(parents.get(term))
    if owner is None or owner.get('class')!='nMux':
        raise ValueError('nMux terminal owner required')
    reference=term.find('dco')
    if reference is None or reference.attrib.keys()!={'uid'} or len(reference):
        raise ValueError('empty UID-only aggregate DCO reference required')
    uid=reference.get('uid')
    definitions=[e for e in root.iter() if e.get('uid')==uid and e.get('class')=='nmxDCO']
    if len(definitions)!=1:
        raise ValueError('unique nmxDCO definition required')
    definition=definitions[0]
    defining_term=parents.get(definition)
    if defining_term is None or defining_term.get('class')!='term' or parents.get(parents.get(defining_term)) is not owner:
        raise ValueError('aggregate definition must belong to same nMux')
    members=[e.get('uid') for e in definition.findall('termList/*')]
    if len(members)!=2 or len(set(members))!=2 or terminal_uid not in members or defining_term.get('uid') not in members:
        raise ValueError('exact two-terminal aggregate membership required')
    aggregate=owner.find('dcoAgg')
    if aggregate is None or aggregate.attrib.keys()!={'uid'} or len(aggregate) or aggregate.get('uid')!=uid:
        raise ValueError('nMux dcoAgg identity required')
    type_desc=definition.findtext('typeDesc')
    if type_desc is None or not type_desc.startswith('TypeID(') or not type_desc.endswith(')') or not type_desc[7:-1].isdigit():
        raise ValueError('explicit saved TypeID required')
    return dict(terminal_uid=terminal_uid,nmux_uid=owner.get('uid'),dco_uid=uid,
        defining_terminal_uid=defining_term.get('uid'),aggregate_terminal_uids=members,
        saved_type_desc=type_desc,terminal_xml=ET.tostring(term,encoding='unicode'),
        definition_xml=ET.tostring(definition,encoding='unicode'),native_runtime_equivalence=False)
