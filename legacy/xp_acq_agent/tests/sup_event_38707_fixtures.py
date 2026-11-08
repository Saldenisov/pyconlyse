"""Portable fresh G70 fixtures. Supplied leaves/storage are hypothetical."""
from elyse_agent import saved_sup_event_38707 as k

def payload(mask=1,busy=False,error_selector=True,stop=False,start=False,reset=False):
    page=[False]*28
    for i in k.PAGE_DBL_FIELDS:page[i]=float(i)+0.25
    page[12]=10.0;page[18]=300.0;page[24]=stop;page[25]=start
    for i,pos in enumerate(k.REQUEST_POSITIONS):page[pos]=bool(mask&(1<<i))
    dps=[False]*29;dps[0]=busy
    reads=dict((uid,None)for uid in k.READ_UIDS);reads['38750']=dps
    native=dict((uid,None)for uid in k.WRITER_UIDS+k.PROPERTY_UIDS+k.WAIT_UIDS)
    unwired=dict((uid,None)for uid in k.UNWIRED_UIDS)
    literals=dict((uid,None)for uid in k.LITERAL_UIDS)
    error=dict(status=True,code=-7,source_hex='00FF4641554C54')
    clean=dict(status=False,code=91,source_hex='FF00')
    active='38989'if not(busy or mask)else k.ARM_ROWS[mask]['writer_uid']if mask in k.ARM_ROWS else None
    if active:
        p=k.WRITER_PORTS[active];native[active]={p['1']:dict(supplied_reference_out=active),p['3']:dict(error)};unwired[p['2']]=dict(clean)
    if mask in k.ARM_ROWS:
        a=k.ARM_ROWS[mask];reads[a['carrier_read_uid']]=[100.0+i for i in range(10)];native[a['wait_uid']]={a['wait_output_face']:dict(supplied_timer=17)}
        literals[a['reference_literal_uid']]=dict(supplied_reference=a['reference_literal_uid']);literals[a['reset_literal_uid']]=reset
    if not(busy or mask):
        literals['38907']=dict(supplied_reference='38907')
        props=[]
        if stop:props.extend(('67577','67619','67657','67698'))
        if start:props.extend(('7002','70250','67505','68962'));literals['84932']=23
        for u in props:
            p=k.PROPERTY_PORTS[u];native[u]={p['1']:dict(unused_reference=u),p['3']:dict(unused_error=u)};unwired[p['0']]=dict(supplied_property_reference=u);unwired[p['2']]=dict(clean)
    if busy and not mask:literals['39257']='00FF';literals['39271']=dict(error)
    completed=[active]if active else None
    if mask in k.ARM_ROWS:completed.append(k.ARM_ROWS[mask]['carrier_write_uid'])
    return dict(source_id=k.SOURCE_ID,source_version=k.SOURCE_VERSION,event_uid=k.EVENT_UID,frame_uid=k.FRAME_UID,
        event_returns={'38726':{'38728':dict(unused_aggregate=True),'38731':dict(unused_event_type=True),'38734':dict(unused_time=True),'38737':dict(unused_reference=True),'38740':dict(unwired_OldVal=True),'38743':page}},
        local_reads=reads,native_returns=native,unwired_inputs=unwired,border_inputs={'38717':None,'38720':None,'38723':None,'38714':17},literal_inputs=literals,intrinsic_outputs={'41026':error_selector},completed_sinks=completed)

def pure_inputs(p):
    ev=p['event_returns']['38726'];new=tuple(ev['38743']);event=k.EventDataReturn(ev['38731'],ev['38734'],ev['38737'],ev['38740'],new,ev['38728'])
    reads=dict(p['local_reads']);reads['38750']=tuple(reads['38750']);literals=dict(p['literal_inputs']);native=p['native_returns'];unwired=dict(p['unwired_inputs'])
    def err(v):return k.ErrorValue(v['status'],v['code'],bytes.fromhex(v['source_hex']))
    writers=dict((u,native[u])for u in k.WRITER_UIDS);props=dict((u,native[u])for u in k.PROPERTY_UIDS);waits=dict((u,native[u])for u in k.WAIT_UIDS)
    mask=sum(1<<i for i,pos in enumerate(k.REQUEST_POSITIONS)if new[pos]);busy=any(reads['38750'])
    active='38989'if not(busy or mask)else k.ARM_ROWS[mask]['writer_uid']if mask in k.ARM_ROWS else None
    if active:
        ports=k.WRITER_PORTS[active];raw=native[active];writers[active]=k.WriterReturn(raw[ports['1']],err(raw[ports['3']]));unwired[ports['2']]=err(unwired[ports['2']])
    if mask in k.ARM_ROWS:
        a=k.ARM_ROWS[mask];reads[a['carrier_read_uid']]=tuple(reads[a['carrier_read_uid']]);waits[a['wait_uid']]=k.WaitReturn(native[a['wait_uid']][a['wait_output_face']])
    if not(busy or mask):
        ids=[]
        if new[24]:ids.extend(('67577','67619','67657','67698'))
        if new[25]:ids.extend(('7002','70250','67505','68962'))
        for uid in ids:
            ports=k.PROPERTY_PORTS[uid];raw=native[uid];props[uid]=k.PropertyReturn(raw[ports['1']],raw[ports['3']]);unwired[ports['2']]=err(unwired[ports['2']])
    if busy and not mask:literals['39257']=bytes.fromhex(literals['39257']);literals['39271']=err(literals['39271'])
    return [event,reads,k.NativeBoundaries(writers,props,waits,unwired,p['border_inputs']),k.IntrinsicBoundaries(p['intrinsic_outputs']['41026']),literals,None if p['completed_sinks']is None else tuple(p['completed_sinks'])]

def project(p):return k.project_event_38707(*pure_inputs(p))
