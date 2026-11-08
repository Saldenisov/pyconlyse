"""Original APP17/5909/53656 explicit0/1 Case and two fixed Sequence bodies.

Four independent C5 read observations; only two are accessed for selected arm.
Leaf returns, literal/ref decoding and completion reports are hypothetical inputs.
"""
import json
from collections import namedtuple
SOURCE_ID='APP-17'
SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID='5909'
FRAME_UID='53656'
ORIGINAL_SHA256='B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B'
URI_BYTES=b'ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96'
ErrorValue=namedtuple('ErrorValue','status code source_bytes')
ARMS = [{'case_frame': '76439',
  'field_position': 22,
  'first': {'data_input': '53934',
            'field': '53904',
            'handler': '54213',
            'handler_error_input': '70702',
            'literal': '79753',
            'mux': '53898',
            'out': '53900',
            'read': '53890',
            'ref': '54139',
            'ref_input': '53910',
            'returned_error_output': '53930',
            'unused_ref_output': '53915',
            'unwired_error_input': '53918',
            'write': '53881',
            'writeface': '53885',
            'writer': '53908'},
  'last': {'data_input': '86042',
           'field': '86024',
           'handler': '86045',
           'handler_error_input': '86075',
           'literal': '86078',
           'mux': '86018',
           'out': '86020',
           'read': '86012',
           'ref': '86088',
           'ref_input': '86030',
           'returned_error_output': '86039',
           'unused_ref_output': '86033',
           'unwired_error_input': '86036',
           'write': '86004',
           'writeface': '86007',
           'writer': '86028'},
  'phase_diagrams': ['77981', '81258', '85997'],
  'selector': 0,
  'sequence_uid': '77973',
  'wait': {'input': '81908',
           'literal': '83199',
           'node': '81888',
           'provided_U32': 1000,
           'unused_output': '81899'}},
 {'case_frame': '56504',
  'field_position': 26,
  'first': {'data_input': '56647',
            'field': '56580',
            'handler': '56650',
            'handler_error_input': '56706',
            'literal': '56550',
            'mux': '56574',
            'out': '56576',
            'read': '56568',
            'ref': '56529',
            'ref_input': '56586',
            'returned_error_output': '56644',
            'unused_ref_output': '56590',
            'unwired_error_input': '56593',
            'write': '56560',
            'writeface': '56563',
            'writer': '56584'},
  'last': {'data_input': '56867',
           'field': '56845',
           'handler': '56870',
           'handler_error_input': '56900',
           'literal': '56817',
           'mux': '56839',
           'out': '56841',
           'read': '56833',
           'ref': '56792',
           'ref_input': '56851',
           'returned_error_output': '56864',
           'unused_ref_output': '56854',
           'unwired_error_input': '56858',
           'write': '56827',
           'writeface': '56830',
           'writer': '56849'},
  'phase_diagrams': ['56523', '56742', '56785'],
  'selector': 1,
  'sequence_uid': '56518',
  'wait': {'input': '56779',
           'literal': '56748',
           'node': '56768',
           'provided_U32': 1000,
           'unused_output': '56773'}}]
UNWIRED = {'53918': 'error',
 '56593': 'error',
 '56661': 'opaque',
 '56664': 'I32',
 '56668': 'bytes',
 '56699': 'U16',
 '56858': 'error',
 '56879': 'opaque',
 '56882': 'I32',
 '56885': 'bytes',
 '56897': 'U16',
 '70677': 'opaque',
 '70682': 'I32',
 '70685': 'bytes',
 '70699': 'U16',
 '86036': 'error',
 '86054': 'opaque',
 '86057': 'I32',
 '86060': 'bytes',
 '86072': 'U16'}
INPUT_ORDER = {'53908': ('53910', '53918', '53934'),
 '54213': ('70677', '70682', '70685', '70699', '70702'),
 '56584': ('56586', '56593', '56647'),
 '56650': ('56661', '56664', '56668', '56699', '56706'),
 '56768': ('56779',),
 '56849': ('56851', '56858', '56867'),
 '56870': ('56879', '56882', '56885', '56897', '56900'),
 '81888': ('81908',),
 '86028': ('86030', '86036', '86042'),
 '86045': ('86054', '86057', '86060', '86072', '86075')}
LEAF_UIDS = ('53908', '54213', '86028', '86045', '81888', '56584', '56650', '56849', '56870', '56768')
SINK_UIDS = ('53881',
 '53908',
 '54213',
 '86004',
 '86028',
 '86045',
 '81888',
 '56560',
 '56584',
 '56650',
 '56827',
 '56849',
 '56870',
 '56768')
UNQUALIFIED_FLAGS=(
    'native_execution_qualified','native_storage_serializer_qualified','native_default_policy_qualified',
    'native_reference_validity_qualified','native_wait_units_or_timing_qualified','native_event_selection_qualified',
    'native_delivery_or_scheduling_qualified','native_atomic_snapshot_qualified','native_callee_equivalence_qualified',
    'native_primitive_coercion_qualified','native_field_index_selection_qualified','native_String_encoding_qualified',
    'whole_event_equivalence','whole_VI_equivalence')

def _exact(value,keys,why):
    if type(value)is not dict or set(value)!=set(keys):raise ValueError(why+'_KEYS')

def _integer(value,lo,hi,why):
    if type(value)is not int or not lo<=value<=hi:raise ValueError(why+'_EXACT_INTEGER_RANGE')
    return value

def _bytes(value):
    if type(value)is not bytes or len(value)>4096:raise ValueError('EXPLICIT_BOUNDED_BYTES')
    return value

def _typed(value,kind):
    if kind=='error':
        if type(value)is not ErrorValue or type(value.status)is not bool:raise ValueError('EXPLICIT_ERROR_VALUE')
        _integer(value.code,-2**31,2**31-1,'ERROR_CODE');_bytes(value.source_bytes)
    elif kind=='bytes':_bytes(value)
    elif kind=='boolean':
        if type(value)is not bool:raise ValueError('EXACT_BOOLEAN')
    elif kind=='I32':_integer(value,-2**31,2**31-1,kind)
    elif kind=='U16':_integer(value,0,65535,kind)
    return value

def _carrier(value):
    if type(value)is not tuple or len(value)!=40 or any(type(v)is not bool for v in value):raise ValueError('EXACT_40_BOOLEAN_TUPLE')
    return value

def _arm(value):
    _integer(value,0,65535,'NEWVAL_U16')
    if value not in (0,1):raise ValueError('UNQUALIFIED_CASE_DEFAULT_OUTSIDE_EXPLICIT_0_1')
    return ARMS[0]if value==0 else ARMS[1]

def _keys(kind,arm):
    parts=(arm['first'],arm['last'])
    if kind=='reads':return tuple(p['read']for p in parts)
    if kind=='literals':return tuple(p['literal']for p in parts)
    if kind=='refs':return tuple(p['ref']for p in parts)
    if kind=='leaves':return (parts[0]['writer'],parts[0]['handler'],arm['wait']['node'],parts[1]['writer'],parts[1]['handler'])
    if kind=='unwired':return tuple(t for uid in _keys('leaves',arm)for t in INPUT_ORDER[uid]if t in UNWIRED)
    if kind=='sinks':return (parts[0]['write'],parts[0]['writer'],parts[0]['handler'],arm['wait']['node'],parts[1]['write'],parts[1]['writer'],parts[1]['handler'])
    raise ValueError('INTERNAL_SOURCE_KEY_KIND')

def _active(value,kind,arm):
    active=set(_keys(kind,arm));allowed={u for a in ARMS for u in _keys(kind,a)}
    if type(value)is not dict or not active<=set(value)or set(value)-allowed:raise ValueError('ACTIVE_'+kind.upper()+'_KEYS')
    return {u:value[u]for u in _keys(kind,arm)}

def _completions(value,arm):
    if type(value)not in(tuple,list)or any(type(u)is not str or u not in _keys('sinks',arm)for u in value):raise ValueError('COMPLETION_OBSERVATION_DOMAIN')
    if len(value)!=len(set(value)):raise ValueError('COMPLETION_OBSERVATION_DUPLICATE')
    return tuple(value)

def project_event_53656(new_value,local_reads,literal_inputs,reference_bindings,native_boundaries,unwired_inputs,event_outputs=None,completed_sinks=()):
    """Direct selected Case arm, carrier copies and three original Sequence phases.

    Explicit0/1 only. Saved SelectDefaultCase bytes01 do not qualify other U16
    values. Completion subsets/order are reports, never feasible execution traces.
    """
    arm=_arm(new_value);completion=_completions(completed_sinks,arm)
    reads=_active(local_reads,'reads',arm);literals=_active(literal_inputs,'literals',arm)
    refs=_active(reference_bindings,'refs',arm);leaves=_active(native_boundaries,'leaves',arm);uw=_active(unwired_inputs,'unwired',arm)
    for value in reads.values():_carrier(value)
    for value in literals.values():_typed(value,'boolean')
    for uid,row in refs.items():
        _exact(row,('stored_URI_bytes','native_reference'),'REFERENCE_'+uid)
        if _bytes(row['stored_URI_bytes'])!=URI_BYTES:raise ValueError('EXACT_STORED_URI_PAYLOAD')
    for uid,row in leaves.items():_exact(row,('outputs',),'LEAF_'+uid)
    for face,value in uw.items():_typed(value,UNWIRED[face])
    for part in(arm['first'],arm['last']):
        out=leaves[part['writer']]['outputs'];_exact(out,(part['unused_ref_output'],part['returned_error_output']),'WRITER_OUTPUT')
        _typed(out[part['returned_error_output']],'error')
    result=dict(source_id=SOURCE_ID,source_version=SOURCE_VERSION,event_uid=EVENT_UID,frame_uid=FRAME_UID,original_sha256=ORIGINAL_SHA256,
        source_case_uid='76431',source_selector_terminal_uid='76455',source_NewVal_terminal_uid='53859',supplied_NewVal=new_value,
        selected_case_frame=arm['case_frame'],sequence_uid=arm['sequence_uid'],source_sequence_actual_diagram_uids=tuple(arm['phase_diagrams']),
        local_reads=[],field_updates=[],local_assignments=[],leaf_observations=[],reference_bindings=[],supplied_unused_event_outputs=event_outputs,
        completed_sinks=completion,completion_observations_are_feasible_trace=False,completion_observations_prove_success=False,
        original_native_execution=False,source_execution=False,native_storage_serializer_qualified=False,native_field_index_selection_qualified=False,
        native_callee_equivalence_qualified=False,native_coercion_qualified=False,native_String_encoding_qualified=False,native_wait_units_or_timing_qualified=False,
        native_reference_validity_qualified=False,native_default_policy_qualified=False,native_atomic_snapshot_qualified=False,whole_event_equivalence=False,whole_VI_equivalence=False,
        actual_absent_structures=('ForLoop','ErrorCase','VariantToData','ArrayMaxMin','InRangeAndCoerce'))
    def observe(uid,phase,explicit):
        ports={t:uw[t]for t in INPUT_ORDER[uid]if t in uw};ports.update(explicit);_exact(ports,INPUT_ORDER[uid],'SOURCE_CALL_'+uid)
        result['leaf_observations'].append(dict(node_uid=uid,sequence_phase=phase,actual_diagram_uid=arm['phase_diagrams'][phase],inputs=ports,
            source_input_order=INPUT_ORDER[uid],supplied_outputs=leaves[uid]['outputs'],callee_or_native_executed=False,
            unused_outputs_are_uninterpreted=uid not in(arm['first']['writer'],arm['last']['writer'])))
    def copy_field(part,phase):
        base=reads[part['read']];i=arm['field_position'];carrier=base[:i]+(literals[part['literal']],)+base[i+1:]
        result['local_reads'].append(dict(node_uid=part['read'],explicit_paramIdx=26,control_terminal_uid='66821',value=base,independent_observation=True))
        result['field_updates'].append(dict(node_uid=part['mux'],field_terminal_uid=part['field'],raw_i_present=True,raw_flattened_field_index=i,typed_position_path=(i,),
            field_label='22 DPA6 b86 Cmd Miroir LASER EN'if i==22 else '26 DPB2 b78 Cmd Miroir LASER HORS',literal_uid=part['literal'],source_literal_raw_hex='01'if phase==0 else '0000',
            decoded_literal_is_hypothetical=True,aggregate_output_terminal_uid=part['out'],value=carrier,native_field_index_selection_qualified=False))
        result['local_assignments'].append(dict(node_uid=part['write'],terminal_uid=part['writeface'],sequence_phase=phase,explicit_paramIdx=26,control_terminal_uid='66821',value=carrier))
        result['reference_bindings'].append(dict(constant_uid=part['ref'],stored_URI_bytes=URI_BYTES,native_reference=refs[part['ref']]['native_reference'],native_reference_decoding_qualified=False))
        observe(part['writer'],phase,{part['ref_input']:refs[part['ref']]['native_reference'],part['data_input']:carrier})
        observe(part['handler'],phase,{part['handler_error_input']:leaves[part['writer']]['outputs'][part['returned_error_output']]})
    copy_field(arm['first'],0)
    observe(arm['wait']['node'],1,{arm['wait']['input']:1000})
    copy_field(arm['last'],2)
    result['provided_data_numeric_literals']={arm['wait']['literal']:dict(raw_hex='000003E8',U32_value=1000)}
    return result

def _hex(value):return ''.join('{:02X}'.format(b)for b in value)

def _json_bytes(value):
    _exact(value,('bytes_hex',),'BYTE_CARRIER');text=value['bytes_hex']
    if type(text)is not str or len(text)>8192 or len(text)%2 or any(c not in'0123456789ABCDEF'for c in text):raise ValueError('CANONICAL_BOUNDED_BYTE_HEX')
    return bytes.fromhex(text)

def _json_error(value):
    _exact(value,('status','code','source_hex'),'ERROR_CARRIER')
    return _typed(ErrorValue(value['status'],value['code'],_json_bytes({'bytes_hex':value['source_hex']})),'error')

def _encode(value,depth=0):
    if depth>16:raise ValueError('JSON_DEPTH')
    if type(value)is ErrorValue:return dict(status=value.status,code=value.code,source_hex=_hex(value.source_bytes))
    if type(value)is bytes:return {'bytes_hex':_hex(_bytes(value))}
    if value is None or type(value)in(bool,str,int):
        if type(value)is str and len(value)>8192:raise ValueError('JSON_STRING_SIZE')
        if type(value)is int and abs(value)>2**53-1:raise ValueError('JSON_INTEGER_RANGE')
        return value
    if type(value)is float:
        if value!=value or value in(float('inf'),-float('inf')):raise ValueError('JSON_NONFINITE')
        return value
    if type(value)in(list,tuple):
        if len(value)>64:raise ValueError('JSON_LIST_SIZE')
        return [_encode(v,depth+1)for v in value]
    if type(value)is dict and len(value)<=64 and all(type(k)is str and len(k)<=128 for k in value):return {k:_encode(v,depth+1)for k,v in value.items()}
    raise ValueError('JSON_INERT_VALUE')

def replay_saved_sup_event_53656(payload):
    required={'source_id','source_version','event_uid','frame_uid','new_value','local_reads','literal_inputs','reference_bindings','native_boundaries','unwired_inputs','unqualified_boundaries'}
    optional={'event_outputs','completed_sinks'}
    if type(payload)is not dict or not required<=set(payload)or set(payload)-required-optional:raise ValueError('PAYLOAD_KEYS')
    if tuple(payload[k]for k in('source_id','source_version','event_uid','frame_uid'))!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('SOURCE_ENTITY_IDENTITY')
    _exact(payload['unqualified_boundaries'],UNQUALIFIED_FLAGS,'BOUNDARY')
    if any(v is not False for v in payload['unqualified_boundaries'].values()):raise ValueError('BOUNDARY_FALSE_REQUIRED')
    _encode(payload)
    arm=_arm(payload['new_value']);reads=_active(payload['local_reads'],'reads',arm)
    if any(type(v)is not list for v in reads.values()):raise ValueError('JSON_40_BOOLEAN_LIST')
    refs=_active(payload['reference_bindings'],'refs',arm);decoded_refs={}
    for uid,row in refs.items():
        _exact(row,('stored_URI_bytes','native_reference'),'REFERENCE_'+uid)
        decoded_refs[uid]=dict(stored_URI_bytes=_json_bytes(row['stored_URI_bytes']),native_reference=row['native_reference'])
    leaves=_active(payload['native_boundaries'],'leaves',arm);decoded_leaves={}
    writer_parts={p['writer']:p for p in(arm['first'],arm['last'])}
    for uid,row in leaves.items():
        _exact(row,('outputs',),'LEAF_'+uid)
        if uid in writer_parts:
            p=writer_parts[uid];out=row['outputs'];_exact(out,(p['unused_ref_output'],p['returned_error_output']),'WRITER_OUTPUT')
            decoded_leaves[uid]=dict(outputs={p['unused_ref_output']:out[p['unused_ref_output']],p['returned_error_output']:_json_error(out[p['returned_error_output']])})
        else:decoded_leaves[uid]=row
    uw=_active(payload['unwired_inputs'],'unwired',arm)
    decoded_uw={uid:_json_error(v)if UNWIRED[uid]=='error'else _json_bytes(v)if UNWIRED[uid]=='bytes'else v for uid,v in uw.items()}
    return _encode(project_event_53656(payload['new_value'],{uid:tuple(v)for uid,v in reads.items()},_active(payload['literal_inputs'],'literals',arm),decoded_refs,decoded_leaves,decoded_uw,
        event_outputs=payload.get('event_outputs'),completed_sinks=payload.get('completed_sinks',())))

__all__=['project_event_53656','replay_saved_sup_event_53656','ErrorValue']
