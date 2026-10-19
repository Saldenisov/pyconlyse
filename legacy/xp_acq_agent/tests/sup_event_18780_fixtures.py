"""Portable fresh frame18780 JSON fixture; no iteration-directory dependency."""
def err(code=0,source='00FF',status=False):
    return dict(status=status,code=code,source_hex=source)

def full_payload():
    old=[float(i)/4 for i in range(33)];new=list(old)
    for i in(0,7,32):new[i]-=0.5
    refs=[{'control':i}for i in range(33)]
    loops=[];reads=[];unwired=[];false=[]
    for i in range(33):
        loops.append({'20125':{'41925':{'loop_ref':i}},'40540':{'40552':{'unused_ref':i},'40570':err(i+1),'40574':list(refs)},'41806':{'41808':{'specific':i},'41811':err(i+2)},'41566':{'41579':{'unused_color_ref':i},'41588':err(i+3)},'20132':{'20138':{'unused_psp_ref':i},'20148':err(i+4,'00FF',True)}})
        reads.append([float(i*100+j)/8 for j in range(33)]);unwired.append(err(-i-1));false.append(err(1000+i,'FE00',True))
    return dict(source_id='APP-17',source_version='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9',event_uid='5909',frame_uid='18780',
        event_returns={'19499':{'19506':{'opaque_aggregate':1},'19613':2,'19667':7,'19672':{'event_ref':1},'19675':old,'19678':new}},
        local_reads={'19687':[False]*29,'19774':reads,'8733':4},loop_returns=loops,
        final_returns={'40447':{'40450':{'final_control_ref':1}},'40236':{'40245':{'unused_final_ref':1},'40259':err(50),'40279':list(refs)},'40404':{'40406':{'specific_final':1},'40409':err(51)},'40371':{'40376':{'unused_numeric_ref':1},'40382':err(52),'55971':'4100FF','57536':{'opaque_variant':1}},'62591':{'62617':err(53),'62646':1.25},'22086':{'53673':'5300FF','53679':err(54,'FF0041',True)}},
        wait_return={'37383':{'unused_timer':1}},unwired_inputs={'40566':unwired},
        border_inputs={'19400':{'unused_reg_out':1},'19464':{'unused_border':1},'19482':{'unused_reg_in':1},'19374':{'unused_attente':1}},
        literal_inputs={'49984':0.0,'47580':2.0,'41829':{'hypothetical_target_class':1},'40424':{'hypothetical_target_class':2},'19972':{'hypothetical_psp_reference':1}},
        intrinsic_outputs={'29467':false,'29296':err(-77,'0001',True),'20154':True},completed_sinks=[['20132',32],['35923',0],['20535',None]])

def decoded(module,p=None):
    """Make direct records independently of replay implementation."""
    p=full_payload()if p is None else p
    def e(raw):return module.ErrorValue(raw['status'],raw['code'],bytes.fromhex(raw['source_hex']))
    def prop(uid,raw):
        names={'40540':('40552','40570',('40574',)),'41566':('41579','41588',()),'40236':('40245','40259',('40279',)),'40371':('40376','40382',('55971','57536'))}
        ref,error,keys=names[uid];values={k:raw[k]for k in keys}
        for k in('40574','40279'):
            if k in values:values[k]=tuple(values[k])
        if'55971'in values:values['55971']=bytes.fromhex(values['55971'])
        return module.PropertyReturn(raw[ref],e(raw[error]),values)
    loops=tuple(module.LoopReturn(r['20125']['41925'],prop('40540',r['40540']),module.CastReturn(r['41806']['41808'],e(r['41806']['41811'])),prop('41566',r['41566']),module.WriterReturn(r['20132']['20138'],e(r['20132']['20148'])))for r in p['loop_returns'])
    f=p['final_returns'];final=module.FinalReturn(f['40447']['40450'],prop('40236',f['40236']),module.CastReturn(f['40404']['40406'],e(f['40404']['40409'])),prop('40371',f['40371']),module.VariantReturn(e(f['62591']['62617']),f['62591']['62646']),module.FormatterReturn(e(f['22086']['53679']),bytes.fromhex(f['22086']['53673'])))
    ev=p['event_returns']['19499'];event=module.EventDataReturn(ev['19613'],ev['19667'],ev['19672'],tuple(ev['19675']),tuple(ev['19678']),ev['19506'])
    reads={'19687':tuple(p['local_reads']['19687']),'19774':tuple(tuple(v)for v in p['local_reads']['19774']),'8733':p['local_reads']['8733']}
    native=module.NativeBoundaries(loops,final,module.WaitReturn(p['wait_return']['37383']),{'40566':tuple(e(v)for v in p['unwired_inputs']['40566'])},p['border_inputs'])
    intrinsic=module.IntrinsicBoundaries(tuple(e(v)for v in p['intrinsic_outputs']['29467']),e(p['intrinsic_outputs']['29296']),p['intrinsic_outputs']['20154'])
    return event,reads,native,intrinsic,dict(p['literal_inputs']),None
