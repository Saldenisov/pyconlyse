"""Original APP17/5909/47072 direct Boolean gate, field copies and byte concat.

Source storage/native/ErrorCase interpretations remain supplied hypotheses.
Independent local DPS read is not inferred from EventData.NewVal.
"""
import json
import math
from collections import namedtuple
SOURCE_ID='APP-17'
SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID='5909'
FRAME_UID='47072'
ORIGINAL_SHA256='B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B'
URI_BYTES=b'ni.var.psp://localhost/SUPERVISION/DPS'
PREFIX_BYTES=b"Erreur de communication avec le SVE pendant l'envoie d'une commande de M/A ou cyclage des alimentations: "
ErrorValue=namedtuple('ErrorValue','status code source_bytes')
UNQUALIFIED_FLAGS=('native_execution_qualified','native_storage_serializer_qualified','native_default_policy_qualified',
    'native_reference_validity_qualified','native_wait_units_or_timing_qualified','native_event_selection_qualified',
    'native_delivery_or_scheduling_qualified','native_atomic_snapshot_qualified','native_callee_equivalence_qualified',
    'native_primitive_coercion_qualified','native_field_index_selection_qualified','native_String_encoding_qualified',
    'native_ErrorCluster_Case_selection_qualified','native_DBL_bitwise_equivalence_qualified','whole_event_equivalence','whole_VI_equivalence')

def _exact(value,keys,why):
    if type(value)is not dict or set(value)!=set(keys):raise ValueError(why+'_KEYS')

def _integer(value,lo,hi,why):
    if type(value)is not int or not lo<=value<=hi:raise ValueError(why+'_EXACT_INTEGER_RANGE')
    return value

def _bytes(value,limit=4096):
    if type(value)is not bytes or len(value)>limit:raise ValueError('EXPLICIT_BOUNDED_BYTES')
    return value

def _error(value):
    if type(value)is not ErrorValue or type(value.status)is not bool:raise ValueError('EXPLICIT_ERROR_VALUE')
    _integer(value.code,-2**31,2**31-1,'ERROR_CODE');_bytes(value.source_bytes)
    return value

def _bool(value):
    if type(value)is not bool:raise ValueError('EXACT_BOOLEAN')
    return value

def _dps(value):
    if type(value)is not tuple or len(value)!=29 or any(type(v)is not bool for v in value):raise ValueError('EXACT_29_BOOLEAN_TUPLE')
    return value

def _page(value):
    if type(value)is not tuple or len(value)!=14:raise ValueError('EXACT_14_FIELD_PAGE_TUPLE')
    graph=value[0]
    if type(graph)is not tuple or len(graph)!=7 or any(type(v)is not float or not math.isfinite(v)for v in graph):raise ValueError('EXACT_7_FINITE_DBL_GRAPH')
    for i in (1,6,7,8,11):_integer(value[i],0,65535,'PAGE_U16')
    for i in (2,3,4,5,9,12,13):_bool(value[i])
    _bytes(value[10])
    return value

def _selected(value,required,allowed,why):
    if type(value)is not dict or not set(required)<=set(value)or set(value)-set(allowed):raise ValueError(why+'_ACTIVE_KEYS')
    return {key:value[key]for key in required}

def _completions(value,allowed):
    if type(value)not in(tuple,list)or any(type(u)is not str or u not in allowed for u in value):raise ValueError('COMPLETION_OBSERVATION_DOMAIN')
    if len(value)!=len(set(value)):raise ValueError('COMPLETION_OBSERVATION_DUPLICATE')
    return tuple(value)

def project_event_47072(new_value,local_reads,literal_inputs,reference_bindings,native_boundaries,unwired_inputs,event_time_40518,intrinsic_inputs,event_outputs=None,completed_sinks=()):
    """Direct typed Boolean business graph and explicit ErrorCase hypothesis.

    Busy branch accesses only its decoded U32 literal and Wait return. Nonbusy
    branch copies three Page fields into independent DPS data, supplies PSP and
    lowers both ErrorCase arms. Completion subsets/order are caller reports.
    """
    _exact(local_reads,('47137',),'LOCAL_READ')
    dps=_dps(local_reads['47137']);busy=any(dps)
    result=dict(source_id=SOURCE_ID,source_version=SOURCE_VERSION,event_uid=EVENT_UID,frame_uid=FRAME_UID,original_sha256=ORIGINAL_SHA256,
        source_case_uid='47154',source_selector_terminal_uid='47156',source_NewVal_terminal_uid='47129',selected_case_frame='47226'if busy else'47168',
        source_busy_gate=dict(local_read_node_uid='47137',ClusterToArray_node_uid='38462',OrArrayElements_node_uid='40386',Boolean_array=dps,any_request=busy),
        local_reads=[dict(node_uid='47137',explicit_paramIdx=176,control_terminal_uid='135295',value=dps,independent_observation=True)],
        field_updates=[],local_assignments=[],leaf_observations=[],case_observations=[],reference_bindings=[],supplied_unused_event_outputs=event_outputs,
        completion_observations_are_feasible_trace=False,completion_observations_prove_success=False,
        original_native_execution=False,source_execution=False,native_storage_serializer_qualified=False,native_field_index_selection_qualified=False,
        native_callee_equivalence_qualified=False,native_coercion_qualified=False,native_String_encoding_qualified=False,native_wait_units_or_timing_qualified=False,
        native_reference_validity_qualified=False,native_default_policy_qualified=False,native_atomic_snapshot_qualified=False,native_ErrorCluster_Case_selection_qualified=False,
        native_DBL_bitwise_equivalence_qualified=False,whole_event_equivalence=False,whole_VI_equivalence=False,
        actual_absent_structures=('ForLoop','Sequence','VariantToData','ArrayMaxMin','InRangeAndCoerce'))
    leaf_keys=('28270',)if busy else('32048','28270')
    leaves=_selected(native_boundaries,leaf_keys,('32048','28270'),'NATIVE_RETURN')
    for row in leaves.values():_exact(row,('outputs',),'LEAF_BOUNDARY')
    if busy:
        literals=_selected(literal_inputs,('42462',),('42462','35281'),'LITERAL')
        wait_value=_integer(literals['42462'],0,2**32-1,'DECODED_42462_U32')
        result['decoded_literal_observations']=[dict(node_uid='42462',raw_hex='0000000000',supplied_decoded_U32=wait_value,native_serializer_qualified=False)]
        allowed=('28270',)
    else:
        page=_page(new_value)
        _exact(intrinsic_inputs,('19594',),'INTRINSIC_SELECTOR');error_arm=_bool(intrinsic_inputs['19594'])
        reference=_selected(reference_bindings,('31390',),('31390',),'REFERENCE')['31390']
        _exact(reference,('stored_URI_bytes','native_reference'),'REFERENCE_31390')
        if _bytes(reference['stored_URI_bytes'])!=URI_BYTES:raise ValueError('EXACT_STORED_URI_PAYLOAD')
        _exact(unwired_inputs,('32658',),'UNWIRED_INPUT');unwired_error=_error(unwired_inputs['32658'])
        out=leaves['32048']['outputs'];_exact(out,('32655','32661'),'WRITER_OUTPUT');returned_error=_error(out['32661'])
        wait_value=_integer(event_time_40518,0,2**32-1,'EVENT_TIME_40518_U32')
        updated=list(dps)
        for source_term,raw_i,path,target_term,target_i in [('47179',11,4,'47204',20),('47182',10,3,'47207',23),('67149',19,12,'68861',21)]:
            value=page[path];updated[target_i]=value
            result['field_updates'].append(dict(source_node_uid='47174',source_terminal_uid=source_term,raw_i_present=True,
                raw_flattened_field_index=raw_i,typed_position_path=(path,),destination_node_uid='47198',destination_terminal_uid=target_term,
                destination_raw_flattened_field_index=target_i,destination_typed_position_path=(target_i,),value=value,native_field_index_selection_qualified=False))
        updated=tuple(updated)
        result['local_assignments'].append(dict(node_uid='47186',terminal_uid='47189',explicit_paramIdx=176,control_terminal_uid='135295',value=updated))
        result['reference_bindings'].append(dict(constant_uid='31390',stored_URI_bytes=URI_BYTES,native_reference=reference['native_reference'],native_reference_decoding_qualified=False))
        result['leaf_observations'].append(dict(node_uid='32048',actual_diagram_uid='47168',source_input_order=('32652','32658','32664'),
            inputs={'32652':reference['native_reference'],'32658':unwired_error,'32664':updated},supplied_outputs=out,callee_or_native_executed=False,unused_outputs_are_uninterpreted=True))
        result['case_observations'].append(dict(node_uid='19594',selector_terminal_uid='36566',source_input_error=returned_error,
            supplied_intrinsic_selector=error_arm,selected_frame='36477'if error_arm else'36498',native_ErrorCluster_projection_qualified=False,
            hypothetical_selector_may_be_incompatible_with_native_execution=True))
        allowed=('47186','32048','28270')
        if error_arm:
            prefix=_selected(literal_inputs,('35281',),('35281','42462'),'LITERAL')['35281'];_bytes(prefix)
            if prefix!=PREFIX_BYTES:raise ValueError('EXACT_35281_PAYLOAD_BYTE_HYPOTHESIS')
            message=prefix+returned_error.source_bytes
            result['decoded_literal_observations']=[dict(node_uid='35281',raw_length_prefix_hex='00000069',supplied_decoded_bytes=prefix,native_serializer_qualified=False)]
            result['byte_concat']=dict(node_uid='37324',ordered_input_terminal_uids=('42382','42385'),output_terminal_uid='42379',
                prefix_bytes=prefix,Error_source_bytes=returned_error.source_bytes,value=message,native_String_semantics_qualified=False)
            result['local_assignments'].append(dict(node_uid='40558',terminal_uid='88706',explicit_paramIdx=184,control_terminal_uid='61053',value=message))
            allowed=allowed+('40558',)
        else:
            # Literal values are not read on the empty ErrorCase arm.
            _selected(literal_inputs,(),('35281','42462'),'LITERAL')
            result['decoded_literal_observations']=[]
        result['event_time_source_observation']=dict(terminal_uid='40518',paired_tunnel_path=('40491','40483','42140','42148'),value=wait_value,source_event_delivery_qualified=False)
    result['completed_sinks']=_completions(completed_sinks,allowed)
    result['leaf_observations'].append(dict(node_uid='28270',actual_diagram_uid='47072',source_input_order=('28277',),
        inputs={'28277':wait_value},supplied_outputs=leaves['28270']['outputs'],callee_or_native_executed=False,unused_outputs_are_uninterpreted=True))
    result['source_Wait_input_value']=wait_value
    return result

def _hex(value):return ''.join('{:02X}'.format(b)for b in value)

def _json_bytes(value):
    _exact(value,('bytes_hex',),'BYTE_CARRIER');text=value['bytes_hex']
    if type(text)is not str or len(text)>8192 or len(text)%2 or any(c not in'0123456789ABCDEF'for c in text):raise ValueError('CANONICAL_BOUNDED_BYTE_HEX')
    return bytes.fromhex(text)

def _json_error(value):
    _exact(value,('status','code','source_hex'),'ERROR_CARRIER')
    return _error(ErrorValue(value['status'],value['code'],_json_bytes({'bytes_hex':value['source_hex']})))

def _encode(value,depth=0):
    if depth>16:raise ValueError('JSON_DEPTH')
    if type(value)is ErrorValue:return dict(status=value.status,code=value.code,source_hex=_hex(value.source_bytes))
    if type(value)is bytes:return {'bytes_hex':_hex(_bytes(value,4201))}
    if value is None or type(value)in(bool,str,int):
        if type(value)is str and len(value)>8402:raise ValueError('JSON_STRING_SIZE')
        if type(value)is int and abs(value)>2**53-1:raise ValueError('JSON_INTEGER_RANGE')
        return value
    if type(value)is float:
        if not math.isfinite(value):raise ValueError('JSON_NONFINITE')
        return value
    if type(value)in(list,tuple):
        if len(value)>64:raise ValueError('JSON_LIST_SIZE')
        return [_encode(v,depth+1)for v in value]
    if type(value)is dict and len(value)<=64 and all(type(k)is str and len(k)<=128 for k in value):return {k:_encode(v,depth+1)for k,v in value.items()}
    raise ValueError('JSON_INERT_VALUE')

def replay_saved_sup_event_47072(payload):
    required={'source_id','source_version','event_uid','frame_uid','new_value','local_reads','literal_inputs','reference_bindings','native_boundaries','unwired_inputs','event_time_40518','intrinsic_inputs','unqualified_boundaries'}
    optional={'event_outputs','completed_sinks'}
    if type(payload)is not dict or not required<=set(payload)or set(payload)-required-optional:raise ValueError('PAYLOAD_KEYS')
    if tuple(payload[k]for k in('source_id','source_version','event_uid','frame_uid'))!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('SOURCE_ENTITY_IDENTITY')
    _exact(payload['unqualified_boundaries'],UNQUALIFIED_FLAGS,'BOUNDARY')
    if any(v is not False for v in payload['unqualified_boundaries'].values()):raise ValueError('BOUNDARY_FALSE_REQUIRED')
    _encode(payload)
    _exact(payload['local_reads'],('47137',),'LOCAL_READ');raw_dps=payload['local_reads']['47137']
    if type(raw_dps)is not list:raise ValueError('JSON_29_BOOLEAN_LIST')
    dps=_dps(tuple(raw_dps));busy=any(dps)
    refs=payload['reference_bindings'];leaves=payload['native_boundaries'];uw=payload['unwired_inputs'];literals=payload['literal_inputs'];newval=payload['new_value']
    if not busy:
        if type(newval)is not list or len(newval)!=14 or type(newval[0])is not list:raise ValueError('JSON_14_FIELD_PAGE_LIST')
        newval=tuple(tuple(newval[0])if i==0 else _json_bytes(v)if i==10 else v for i,v in enumerate(newval))
        _exact(refs,('31390',),'REFERENCE')
        row=refs['31390'];_exact(row,('stored_URI_bytes','native_reference'),'REFERENCE_31390')
        refs={'31390':dict(stored_URI_bytes=_json_bytes(row['stored_URI_bytes']),native_reference=row['native_reference'])}
        _exact(uw,('32658',),'UNWIRED_INPUT');uw={'32658':_json_error(uw['32658'])}
        selected=_selected(leaves,('32048','28270'),('32048','28270'),'NATIVE_RETURN')
        row=selected['32048'];_exact(row,('outputs',),'LEAF_BOUNDARY');out=row['outputs'];_exact(out,('32655','32661'),'WRITER_OUTPUT')
        leaves=dict(selected);leaves['32048']=dict(outputs={'32655':out['32655'],'32661':_json_error(out['32661'])})
        if type(payload['intrinsic_inputs'])is dict and payload['intrinsic_inputs'].get('19594')is True:
            selected_literals=_selected(literals,('35281',),('35281','42462'),'LITERAL')
            literals=dict(literals);literals['35281']=_json_bytes(selected_literals['35281'])
    return _encode(project_event_47072(newval,{'47137':dps},literals,refs,leaves,uw,payload['event_time_40518'],payload['intrinsic_inputs'],
        event_outputs=payload.get('event_outputs'),completed_sinks=payload.get('completed_sinks',())))

__all__=['project_event_47072','replay_saved_sup_event_47072','ErrorValue']
