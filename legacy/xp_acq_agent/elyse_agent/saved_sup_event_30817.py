"""Original APP17/5909/30817 direct Boolean gate, eleven copies and byte concat.

Native storage, references, ErrorCluster selector and delivery remain hypotheses.
Independent DPS read is not inferred from EventData.NewVal.
"""
import json
from collections import namedtuple
SOURCE_ID='APP-17'
SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID='5909'
FRAME_UID='30817'
ORIGINAL_SHA256='B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B'
URI_BYTES=b'ni.var.psp://localhost/SUPERVISION/DPS'
PREFIX_BYTES=b"Erreur de communication avec le SVE pendant l'envoie d'une commande de M/A du modulateur."
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

def _finite(value):return value==value and value not in(float('inf'),float('-inf'))

def _dps(value):
    if type(value)is not tuple or len(value)!=29 or any(type(v)is not bool for v in value):raise ValueError('EXACT_29_BOOLEAN_TUPLE')
    return value

def _page(value):
    if type(value)is not tuple or len(value)!=59:raise ValueError('EXACT_59_FIELD_PAGE_TUPLE')
    for i in range(59):
        if 31<=i<=44:
            if type(value[i])is not float or not _finite(value[i]):raise ValueError('EXACT_FINITE_DBL_PAGE_FIELD')
        else:_bool(value[i])
    return value

def _selected(value,required,allowed,why):
    if type(value)is not dict or not set(required)<=set(value)or set(value)-set(allowed):raise ValueError(why+'_ACTIVE_KEYS')
    return {key:value[key]for key in required}

def _completions(value,allowed):
    if type(value)not in(tuple,list)or any(type(u)is not str or u not in allowed for u in value):raise ValueError('COMPLETION_OBSERVATION_DOMAIN')
    if len(value)!=len(set(value)):raise ValueError('COMPLETION_OBSERVATION_DUPLICATE')
    return tuple(value)

def project_event_30817(new_value,local_reads,literal_inputs,reference_bindings,native_boundaries,unwired_inputs,event_time_30833,intrinsic_inputs,event_outputs=None,completed_sinks=()):
    """Direct selected structures within explicit typed caller domains.

    Busy path reads only supplied literal42193 and Wait43942 return. Nonbusy
    copies eleven Boolean Page fields into independent DPS, then uses supplied
    PSP/ErrorCase boundaries and direct byte concat. Completion subsets/order
    are caller observations, not feasible schedules or success assertions.
    """
    _exact(local_reads,('30929',),'LOCAL_READ')
    dps=_dps(local_reads['30929']);busy=any(dps)
    result=dict(source_id=SOURCE_ID,source_version=SOURCE_VERSION,event_uid=EVENT_UID,frame_uid=FRAME_UID,original_sha256=ORIGINAL_SHA256,
        source_case_uid='30946',source_selector_terminal_uid='30951',source_NewVal_terminal_uid='30915',selected_case_frame='42181'if busy else'31001',
        source_busy_gate=dict(local_read_node_uid='30929',ClusterToArray_node_uid='43109',OrArrayElements_node_uid='43129',Boolean_array=dps,any_request=busy),
        local_reads=[dict(node_uid='30929',explicit_paramIdx=176,control_terminal_uid='135295',value=dps,independent_observation=True)],
        field_updates=[],local_assignments=[],leaf_observations=[],case_observations=[],reference_bindings=[],supplied_unused_event_outputs=event_outputs,
        completion_observations_are_feasible_trace=False,completion_observations_prove_success=False,
        original_native_execution=False,source_execution=False,native_storage_serializer_qualified=False,native_field_index_selection_qualified=False,
        native_callee_equivalence_qualified=False,native_coercion_qualified=False,native_String_encoding_qualified=False,native_wait_units_or_timing_qualified=False,
        native_reference_validity_qualified=False,native_default_policy_qualified=False,native_atomic_snapshot_qualified=False,native_ErrorCluster_Case_selection_qualified=False,
        native_DBL_bitwise_equivalence_qualified=False,whole_event_equivalence=False,whole_VI_equivalence=False,
        actual_absent_structures=('ForLoop','Sequence','VariantToData','ArrayMaxMin','InRangeAndCoerce'))
    leaf_keys=('43942',)if busy else('33792','43942')
    leaves=_selected(native_boundaries,leaf_keys,('33792','43942'),'NATIVE_RETURN')
    for row in leaves.values():_exact(row,('outputs',),'LEAF_BOUNDARY')
    if busy:
        literals=_selected(literal_inputs,('42193',),('42193','34420'),'LITERAL')
        wait_value=_integer(literals['42193'],0,2**32-1,'DECODED_42193_U32')
        result['decoded_literal_observations']=[dict(node_uid='42193',raw_hex='0000000000',supplied_decoded_U32=wait_value,native_serializer_qualified=False)]
        allowed=('43942',)
    else:
        page=_page(new_value)
        _exact(intrinsic_inputs,('33976',),'INTRINSIC_SELECTOR');error_arm=_bool(intrinsic_inputs['33976'])
        reference=_selected(reference_bindings,('31469',),('31469',),'REFERENCE')['31469']
        _exact(reference,('stored_URI_bytes','native_reference'),'REFERENCE_31469')
        if _bytes(reference['stored_URI_bytes'])!=URI_BYTES:raise ValueError('EXACT_STORED_URI_PAYLOAD')
        _exact(unwired_inputs,('33899',),'UNWIRED_INPUT');unwired_error=_error(unwired_inputs['33899'])
        out=leaves['33792']['outputs'];_exact(out,('33864','33926'),'WRITER_OUTPUT');returned_error=_error(out['33926'])
        wait_value=_integer(event_time_30833,0,2**32-1,'EVENT_TIME_30833_U32')
        updated=list(dps)
        mappings=(('32208',22,'33493',2),('32239',23,'33501',3),('54314',46,'60109',4),('57159',47,'60114',5),
            ('57855',48,'60117',6),('57860',49,'60120',7),('57863',50,'60123',8),('57866',51,'60126',9),
            ('57869',52,'60129',10),('57872',53,'60132',11),('57875',21,'60135',12))
        for source_term,source_i,target_term,target_i in mappings:
            value=page[source_i];updated[target_i]=value
            result['field_updates'].append(dict(source_node_uid='32126',source_terminal_uid=source_term,raw_i_present=True,
                raw_flattened_field_index=source_i,typed_position_path=(source_i,),destination_node_uid='33466',destination_terminal_uid=target_term,
                destination_raw_flattened_field_index=target_i,destination_typed_position_path=(target_i,),value=value,native_field_index_selection_qualified=False))
        updated=tuple(updated)
        result['local_assignments'].append(dict(node_uid='33453',terminal_uid='33461',explicit_paramIdx=176,control_terminal_uid='135295',value=updated))
        result['reference_bindings'].append(dict(constant_uid='31469',stored_URI_bytes=URI_BYTES,native_reference=reference['native_reference'],native_reference_decoding_qualified=False))
        result['leaf_observations'].append(dict(node_uid='33792',actual_diagram_uid='31001',source_input_order=('33804','33899','33954'),
            inputs={'33804':reference['native_reference'],'33899':unwired_error,'33954':updated},supplied_outputs=out,callee_or_native_executed=False,unused_outputs_are_uninterpreted=True))
        result['case_observations'].append(dict(node_uid='33976',selector_terminal_uid='33992',source_input_error=returned_error,
            supplied_intrinsic_selector=error_arm,selected_frame='34401'if error_arm else'34174',native_ErrorCluster_projection_qualified=False,
            hypothetical_selector_may_be_incompatible_with_native_execution=True))
        allowed=('33453','33792','43942')
        if error_arm:
            prefix=_selected(literal_inputs,('34420',),('34420','42193'),'LITERAL')['34420'];_bytes(prefix)
            if prefix!=PREFIX_BYTES:raise ValueError('EXACT_34420_PAYLOAD_BYTE_HYPOTHESIS')
            message=prefix+returned_error.source_bytes
            result['decoded_literal_observations']=[dict(node_uid='34420',raw_length_prefix_hex='00000059',supplied_decoded_bytes=prefix,native_serializer_qualified=False)]
            result['byte_concat']=dict(node_uid='37074',ordered_input_terminal_uids=('37567','37575'),output_terminal_uid='37554',
                prefix_bytes=prefix,Error_source_bytes=returned_error.source_bytes,value=message,native_String_semantics_qualified=False)
            result['local_assignments'].append(dict(node_uid='37686',terminal_uid='37702',explicit_paramIdx=184,control_terminal_uid='61053',value=message))
            allowed=allowed+('37686',)
        else:
            _selected(literal_inputs,(),('34420','42193'),'LITERAL')
            result['decoded_literal_observations']=[]
        result['event_time_source_observation']=dict(terminal_uid='30833',paired_tunnel_path=('30979','30984','30994','30988'),value=wait_value,source_event_delivery_qualified=False)
    result['completed_sinks']=_completions(completed_sinks,allowed)
    result['leaf_observations'].append(dict(node_uid='43942',actual_diagram_uid='30817',source_input_order=('45346',),
        inputs={'45346':wait_value},supplied_outputs=leaves['43942']['outputs'],callee_or_native_executed=False,unused_outputs_are_uninterpreted=True))
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
    if type(value)is bytes:return {'bytes_hex':_hex(_bytes(value,4185))}
    if value is None or type(value)in(bool,str,int):
        if type(value)is str and len(value)>8402:raise ValueError('JSON_STRING_SIZE')
        if type(value)is int and abs(value)>2**53-1:raise ValueError('JSON_INTEGER_RANGE')
        return value
    if type(value)is float:
        if not _finite(value):raise ValueError('JSON_NONFINITE')
        return value
    if type(value)in(list,tuple):
        if len(value)>64:raise ValueError('JSON_LIST_SIZE')
        return [_encode(v,depth+1)for v in value]
    if type(value)is dict and len(value)<=64 and all(type(k)is str and len(k)<=128 for k in value):return {k:_encode(v,depth+1)for k,v in value.items()}
    raise ValueError('JSON_INERT_VALUE')

def replay_saved_sup_event_30817(payload):
    required={'source_id','source_version','event_uid','frame_uid','new_value','local_reads','literal_inputs','reference_bindings','native_boundaries','unwired_inputs','event_time_30833','intrinsic_inputs','unqualified_boundaries'}
    optional={'event_outputs','completed_sinks'}
    if type(payload)is not dict or not required<=set(payload)or set(payload)-required-optional:raise ValueError('PAYLOAD_KEYS')
    if tuple(payload[k]for k in('source_id','source_version','event_uid','frame_uid'))!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('SOURCE_ENTITY_IDENTITY')
    _exact(payload['unqualified_boundaries'],UNQUALIFIED_FLAGS,'BOUNDARY')
    if any(v is not False for v in payload['unqualified_boundaries'].values()):raise ValueError('BOUNDARY_FALSE_REQUIRED')
    _encode(payload)
    _exact(payload['local_reads'],('30929',),'LOCAL_READ');raw_dps=payload['local_reads']['30929']
    if type(raw_dps)is not list:raise ValueError('JSON_29_BOOLEAN_LIST')
    dps=_dps(tuple(raw_dps));busy=any(dps)
    refs=payload['reference_bindings'];leaves=payload['native_boundaries'];uw=payload['unwired_inputs'];literals=payload['literal_inputs'];newval=payload['new_value']
    if not busy:
        if type(newval)is not list or len(newval)!=59:raise ValueError('JSON_59_FIELD_PAGE_LIST')
        newval=tuple(newval)
        _exact(refs,('31469',),'REFERENCE')
        row=refs['31469'];_exact(row,('stored_URI_bytes','native_reference'),'REFERENCE_31469')
        refs={'31469':dict(stored_URI_bytes=_json_bytes(row['stored_URI_bytes']),native_reference=row['native_reference'])}
        _exact(uw,('33899',),'UNWIRED_INPUT');uw={'33899':_json_error(uw['33899'])}
        selected=_selected(leaves,('33792','43942'),('33792','43942'),'NATIVE_RETURN')
        row=selected['33792'];_exact(row,('outputs',),'LEAF_BOUNDARY');out=row['outputs'];_exact(out,('33864','33926'),'WRITER_OUTPUT')
        leaves=dict(selected);leaves['33792']=dict(outputs={'33864':out['33864'],'33926':_json_error(out['33926'])})
        if type(payload['intrinsic_inputs'])is dict and payload['intrinsic_inputs'].get('33976')is True:
            selected_literals=_selected(literals,('34420',),('34420','42193'),'LITERAL')
            literals=dict(literals);literals['34420']=_json_bytes(selected_literals['34420'])
    return _encode(project_event_30817(newval,{'30929':dps},literals,refs,leaves,uw,payload['event_time_30833'],payload['intrinsic_inputs'],
        event_outputs=payload.get('event_outputs'),completed_sinks=payload.get('completed_sinks',())))

__all__=['project_event_30817','replay_saved_sup_event_30817','ErrorValue']
