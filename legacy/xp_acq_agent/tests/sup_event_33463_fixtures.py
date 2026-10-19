"""Portable inline G69 data; no original native/default feasibility asserted."""
import copy
from elyse_agent import saved_sup_event_33463 as k
def cluster(value=0.5,selector=False,mark=False):
    return [mark,False,True,False,selector,float(value),float(value+0.25),False,False,False,False]
def carrier(base):return [float(base+i)for i in range(10)]
def error(status=True,code=17,source='0046FF'):return dict(status=status,code=code,source_hex=source)
def payload(mask=128,index=0,selector=False,current=0.5,error_selector=True,tie_index=None):
    old=[cluster(i+0.5)for i in range(9)];new=copy.deepcopy(old)
    for bit in range(11):
        if mask&(1<<bit):new[index][bit]=not old[index][bit]if bit in k.BOOL_FIELDS else old[index][bit]+0.125
    nr={'33897':{'33900':{'ctl_reference':'supplied_original_ddo83226'}},
        '33905':{'33907':{'cast_reference':'supplied'},'33910':error(True,21,'00AA')},
        '33859':{'33873':{'unused_reference':'cluster_property'},'33886':error(True,22,'00BB'),'33889':[{'selected_reference':i}for i in range(9)]},
        '33966':{'33971':{'unused_reference':'current_property'},'33977':error(True,23,'00CC'),'33980':{'opaque_variant':'independent_native_observation'}},
        '65169':{'65177':error(True,24,'00DD'),'65191':cluster(current,selector,True)},
        '33935':{'33940':{'unused_reference':'updated_property'},'33946':error(True,-91,'00FF')},
        '46420':{'46422':{'unused_timer':'70_return'}},'27840':{'27846':{'unused_timer':'100_return'}}}
    unwired={'33919':error(True,35,'E901')}
    literals={'33526':cluster(-7.5,False,False),'33630':{'hypothetical_decoded_ref':'raw5zeros'},'46410':False}
    for row in k.WRITER_ROWS:
        nr[row[1]]={row[4]:{'unused_writer_ref':row[1]},row[6]:error(True,-int(row[1]),'00A5FF')}
        nr[row[8]]={u:{'unused_callee_output':u}for u in row[11]}
        unwired[row[5]]=error(False,39,'FF00')
        for u in row[9]:unwired[u]={'hypothetical_unwired_native_input':u}
        literals[row[2]]={'hypothetical_decoded_PSP_reference':row[2]}
    reads={'46585':[cluster(100+i)for i in range(9)],'46632':carrier(200),'46671':carrier(300),
        '46864':carrier(400),'46903':carrier(500),'46942':carrier(600),'46981':carrier(700)}
    completion=['47073','33935']
    if mask>=128:completion.append('46665')
    if error_selector:completion.append('48604')
    return dict(source_id=k.SOURCE_ID,source_version=k.SOURCE_VERSION,event_uid=k.EVENT_UID,frame_uid=k.FRAME_UID,
        event_returns={'33480':{'33482':{'unused_aggregate':True},'33485':{'unused_event_type':True},'33488':{'unused_time':True},'33491':{'unused_event_control_reference':True},'33494':old,'33497':new}},
        local_reads=reads,native_returns=nr,unwired_inputs=unwired,border_inputs={u:{'unused_border':u}for u in k.BORDER_UIDS},literal_inputs=literals,
        intrinsic_outputs={'33835':tie_index,'48544':error_selector},completed_sinks=completion)
def minimum_unique_payload():return payload(mask=1,error_selector=False)
def hypothetical_zero_payload(index=0):return payload(mask=0,error_selector=False,tie_index=index)
def sparse_payload():
    p=minimum_unique_payload()
    for uid in('46585','46632','46671'):p['local_reads'][uid]={'inactive_opaque_carrier':uid}
    p['intrinsic_outputs']['33835']={'unused_tie_policy':True}
    return p
def direct(p):
    """JSON adapter test factory retains original objects for identity checks."""
    def e(v):return k.ErrorValue(v['status'],v['code'],bytes.fromhex(v['source_hex']))
    ev=p['event_returns']['33480'];to=lambda x:tuple(to(y)for y in x)if type(x)is list else x
    event=k.EventDataReturn(ev['33485'],ev['33488'],ev['33491'],to(ev['33494']),to(ev['33497']),ev['33482'])
    nr=p['native_returns'];reads={u:to(v)for u,v in p['local_reads'].items()};literal=dict(p['literal_inputs']);literal['33526']=to(literal['33526']);uw=dict(p['unwired_inputs'])
    for u in('33919',)+tuple(r[5]for r in k.WRITER_ROWS):uw[u]=e(uw[u])
    prop=lambda uid,ref,err,keys:k.PropertyReturn(nr[uid][ref],e(nr[uid][err]),{key:to(nr[uid][key])for key in keys})
    writers={r[1]:k.WriterReturn(nr[r[1]][r[4]],e(nr[r[1]][r[6]]))for r in k.WRITER_ROWS}
    handlers={r[8]:k.CalleeReturn(nr[r[8]])for r in k.WRITER_ROWS}
    native=k.NativeBoundaries(nr['33897']['33900'],k.CastReturn(nr['33905']['33907'],e(nr['33905']['33910'])),prop('33859','33873','33886',('33889',)),prop('33966','33971','33977',('33980',)),k.VariantReturn(e(nr['65169']['65177']),to(nr['65169']['65191'])),prop('33935','33940','33946',()),k.WaitReturn(nr['46420']['46422']),k.WaitReturn(nr['27840']['27846']),writers,handlers,uw,p['border_inputs'])
    i=p['intrinsic_outputs'];return(event,reads,native,k.IntrinsicBoundaries(i['33835'],i['48544']),literal,None if p['completed_sinks']is None else tuple(p['completed_sinks']))
