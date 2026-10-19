"""Saved Acquisition DPS pure facets; no property, event, PSP or hardware calls."""

# Source-specific target and tail constants are generated from the pinned
# independently validated source proof; executable bodies below stay explicit.
TARGETS = (('59266', 3), ('59274', 4), ('59370', 5), ('59378', 6), ('66579', 12), ('66587', 7), ('66627', 13), ('66635', 8), ('66675', 14), ('66683', 9), ('66723', 15), ('66731', 10), ('59386', 11), ('59482', 18), ('59474', 19), ('59314', 20), ('59330', 22), ('59322', 21), ('59426', 23), ('59434', 24), ('66411', 16), ('66443', 25), ('66459', None), ('66419', 17))
TAILS = {3: (0, '5681', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '24540', '18950'), 4: (1, '23177', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '22878', '23117'), 5: (2, '35620', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '35413', '35570'), 6: (3, '37694', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '28661', '35146'), 7: (5, '25625', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '24497', '25430'), 8: (7, '28312', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '26962', '27900'), 9: (9, '31532', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '31360', '31482'), 10: (11, '24161', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '23880', '24054'), 11: (12, '34036', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '33828', '33986'), 12: (4, '38642', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '38483', '38592'), 13: (6, '29442', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '29025', '29203'), 14: (8, '36493', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '36334', '36443'), 15: (10, '40623', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '40463', '40573'), 16: (20, '39486', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '32196', '32353'), 17: (23, '43112', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '42901', '41314'), 18: (13, '35884', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '35506', '35833'), 19: (14, '43962', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '43785', '43894'), 20: (15, '47263', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '54126', '54238'), 21: (17, '32541', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '32123', '32374'), 22: (16, '33509', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '33217', '33438'), 23: (18, '45451', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '45276', '45385'), 24: (19, '41354', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '41162', '41284'), 25: (21, '39861', 'ni.var.psp://10.20.30.2/SUPERVISION/DPS', '39387', '39743')}


def boolean_bank(value):
    if type(value) is not tuple or len(value)!=29 or any(type(bit) is not bool for bit in value):
        raise TypeError('explicit 29-Boolean DPS snapshot required')


def dispatch_values(dps_snapshot):
    """First True in29 fields; unmatched selectors use saved frame0/ACTION False.

    Original selector8105 default0/frame9471 is statically corroborated on
    import20.0.1f1. Literal85221/raw0000 -> wire42492 -> local19100/bank35.
    This pure assignment does not qualify original12 native execution.
    """
    boolean_bank(dps_snapshot)
    first=next((i for i,asserted in enumerate(dps_snapshot) if asserted),-1)
    selector=first+1
    if selector==0:
        return first,selector,'NO_REQUEST',False,None,None
    if selector>len(TARGETS):
        return first,selector,'SAVED_DEFAULT',False,None,None
    ddo,event=TARGETS[first]
    return first,selector,'EXPLICIT_PROPERTY',None,ddo,event


def reset_values(dps_snapshot,event_index):
    """Clear one local request bit after supplied reachability of reset frame."""
    boolean_bank(dps_snapshot)
    if type(event_index) is not int or event_index not in TAILS:
        raise ValueError('implemented event3..25 required')
    result=list(dps_snapshot)
    result[TAILS[event_index][0]]=False
    return tuple(result)


def publication_values(dps_snapshot,event_index):
    """Next frame reads its own snapshot; no reset-snapshot identity assumption."""
    boolean_bank(dps_snapshot)
    if type(event_index) is not int or event_index not in TAILS:
        raise ValueError('implemented event3..25 required')
    return TAILS[event_index][1],TAILS[event_index][2],dps_snapshot


def replay_saved_dispatch(payload):
    if type(payload) is not dict or set(payload)!=set(('source_id','uid','facet','dps','event_index')):
        raise ValueError('exact saved dispatch fields required')
    if payload['source_id']!='APP-00':
        raise ValueError('APP-00 source required')
    data=payload['dps']
    if type(data) is not list:
        raise ValueError('explicit JSON Boolean bank required')
    data=tuple(data)
    facet=payload['facet']
    event=payload['event_index']
    if facet=='dispatch':
        if payload['uid']!='8105' or event is not None:
            raise ValueError('dispatcher8105 with absent event_index required')
        first,selector,kind,action,ddo,registered=dispatch_values(data)
        outputs=dict(first_true_index=first,case_selector=selector,bank43_assignment=first,state=kind,
            action_assignment=action,property_target=ddo,registered_event=registered,
            property_assignments=[['Value',True],['Val(Sgnl)',True]] if kind=='EXPLICIT_PROPERTY' else [],
            unknown_case_outputs=kind=='UNRESOLVED_DEFAULT')
    elif facet in ('reset','publication'):
        if type(event) is not int or event not in TAILS or payload['uid']!=TAILS[event][3 if facet=='reset' else 4]:
            raise ValueError('matching implemented event index/UID required')
        if facet=='reset':
            outputs=dict(local_dps=list(reset_values(data,event)),dps_index=TAILS[event][0])
        else:
            writer,uri,value=publication_values(data,event)
            outputs=dict(writer_uid=writer,uri=uri,data=list(value),publication_executed=False)
    else:
        raise ValueError('known saved dispatch facet required')
    return dict(source_id='APP-00',uid=payload['uid'],facet=facet,outputs=outputs,
        execution_allowed=False,external_calls_executed=False,hardware_writes=False,
        psp_delivery_qualified=False,event_acknowledgement_qualified=False,
        atomic_snapshots_qualified=False,frame_reachability_supplied=True,
        whole_event_equivalence=False,native_runtime_equivalence=False)
