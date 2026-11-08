"""Bounded original saved [16] "Page HF": Value Change body.

Nine local observations are independent. PageHF writes copy EventData.NewVal,
not a PageHF read. Native writer/Wait returns, references, unwired inputs,
error selector and unresolved stored literals are explicitly supplied.
Only finite strict-interior InRange/coerce DBL output is evaluated; its unused
Boolean output, source mode, endpoints, outside ranges, native storage and
coercion are unqualified. Completion observations are caller subsets in
reported order, not feasible schedules, success or execution receipts.
"""
from collections import namedtuple
import math
import struct

SOURCE_ID='APP-17'
SOURCE_VERSION='D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9'
EVENT_UID='5909';FRAME_UID='53716';SAVED_CAPTION='[16] "Page HF": Value Change'
REQUEST_PATHS=(2,4,3,1,14,16,15,13)
PAGE_FLOAT_FIELDS=(0,5,12,17,22,23,24)
NUMERIC_ABS_BOUND=float(2**40)
LITERAL_UIDS=('58402','55804','55821')
BRANCHES={1: {'arith': '56367', 'resid': 1051, 'arith_out': '56369', 'delta_uid': '56297', 'coerce': '56435', 'coerce_out': '56440', 'c8read': '56421', 'c8write': '56325', 'c8bundle': '56397', 'pagewrite': '58321', 'pagebundle': '58290', 'writer': '56337', 'reference_uid': '56258', 'wait': '58355', 'sequence': '58433', 'sequence_diag': '58339', 'page_field': 5, 'c8_field': 4, 'prefix_uid': '56309'}, 2: {'arith': '74075', 'resid': 1051, 'arith_out': '74077', 'delta_uid': '74230', 'coerce': '74102', 'coerce_out': '74107', 'c8read': '74096', 'c8write': '74041', 'c8bundle': '74086', 'pagewrite': '74207', 'pagebundle': '74167', 'writer': '74049', 'reference_uid': '74242', 'wait': '74147', 'sequence': '74216', 'sequence_diag': '74131', 'page_field': 5, 'c8_field': 4, 'prefix_uid': '74219'}, 4: {'arith': '51397', 'resid': 1050, 'arith_out': '54105', 'delta_uid': '53059', 'coerce': '52918', 'coerce_out': '52925', 'c8read': '52907', 'c8write': '52850', 'c8bundle': '52896', 'pagewrite': '53024', 'pagebundle': '52981', 'writer': '52858', 'reference_uid': '53072', 'wait': '52966', 'sequence': '53036', 'sequence_diag': '52950', 'page_field': 5, 'c8_field': 4, 'prefix_uid': '53044'}, 8: {'arith': '68795', 'resid': 1050, 'arith_out': '68797', 'delta_uid': '68821', 'coerce': '68568', 'coerce_out': '68573', 'c8read': '68562', 'c8write': '57063', 'c8bundle': '68552', 'pagewrite': '68787', 'pagebundle': '68679', 'writer': '68526', 'reference_uid': '68833', 'wait': '68627', 'sequence': '68807', 'sequence_diag': '68597', 'page_field': 5, 'c8_field': 4, 'prefix_uid': '68810'}, 16: {'arith': '26839', 'resid': 1051, 'arith_out': '52892', 'delta_uid': '58805', 'coerce': '58641', 'coerce_out': '58646', 'c8read': '58635', 'c8write': '58078', 'c8bundle': '58624', 'pagewrite': '58742', 'pagebundle': '58707', 'writer': '58597', 'reference_uid': '58851', 'wait': '58692', 'sequence': '58768', 'sequence_diag': '58671', 'page_field': 17, 'c8_field': 3, 'prefix_uid': '58778'}, 32: {'arith': '59269', 'resid': 1051, 'arith_out': '59274', 'delta_uid': '59337', 'coerce': '59005', 'coerce_out': '59016', 'c8read': '58995', 'c8write': '58947', 'c8bundle': '58982', 'pagewrite': '59254', 'pagebundle': '59175', 'writer': '58956', 'reference_uid': '59355', 'wait': '59151', 'sequence': '59301', 'sequence_diag': '59113', 'page_field': 17, 'c8_field': 3, 'prefix_uid': '59307'}, 64: {'arith': '58370', 'resid': 1050, 'arith_out': '65121', 'delta_uid': '63264', 'coerce': '63106', 'coerce_out': '63114', 'c8read': '63099', 'c8write': '63050', 'c8bundle': '63088', 'pagewrite': '63225', 'pagebundle': '63176', 'writer': '63059', 'reference_uid': '63286', 'wait': '63159', 'sequence': '63249', 'sequence_diag': '63141', 'page_field': 17, 'c8_field': 3, 'prefix_uid': '63252'}, 128: {'arith': '71649', 'resid': 1050, 'arith_out': '71651', 'delta_uid': '71675', 'coerce': '71544', 'coerce_out': '71549', 'c8read': '71538', 'c8write': '71494', 'c8bundle': '71528', 'pagewrite': '71641', 'pagebundle': '71606', 'writer': '71502', 'reference_uid': '71687', 'wait': '71591', 'sequence': '71661', 'sequence_diag': '71573', 'page_field': 17, 'c8_field': 3, 'prefix_uid': '71664'}}
LOCAL_IDENTITIES={'52850': ('67056', 24, '67054'), '52907': ('67056', 24, '67054'), '53024': ('36922', 167, '36920'), '53769': ('135295', 176, '135293'), '55371': ('135295', 176, '135293'), '56325': ('67056', 24, '67054'), '56421': ('67056', 24, '67054'), '57063': ('67056', 24, '67054'), '58078': ('67056', 24, '67054'), '58262': ('61053', 184, '61051'), '58321': ('36922', 167, '36920'), '58635': ('67056', 24, '67054'), '58742': ('36922', 167, '36920'), '58947': ('67056', 24, '67054'), '58995': ('67056', 24, '67054'), '59254': ('36922', 167, '36920'), '63050': ('67056', 24, '67054'), '63099': ('67056', 24, '67054'), '63225': ('36922', 167, '36920'), '68562': ('67056', 24, '67054'), '68787': ('36922', 167, '36920'), '71494': ('67056', 24, '67054'), '71538': ('67056', 24, '67054'), '71641': ('36922', 167, '36920'), '74041': ('67056', 24, '67054'), '74096': ('67056', 24, '67054'), '74207': ('36922', 167, '36920')}
READ_UIDS=('52907', '53769', '56421', '58635', '58995', '63099', '68562', '71538', '74096')
WRITER_UIDS=('52858', '55466', '56337', '58597', '58956', '63059', '68526', '71502', '74049')
WAIT_UIDS=('52966', '58355', '58692', '59151', '63159', '68627', '71591', '74147')
WRITER_PORTS={'52858': ('52860', '52864', '52867', '52870', '52873'), '55466': ('55469', '55475', '55482', '55492', '55500'), '56337': ('56342', '56346', '56349', '56352', '56355'), '58597': ('58599', '58602', '58605', '58608', '58611'), '58956': ('58958', '58961', '58964', '58967', '58970'), '63059': ('63061', '63064', '63068', '63071', '63074'), '68526': ('68528', '68531', '68534', '68537', '68540'), '71502': ('71504', '71507', '71510', '71513', '71516'), '74049': ('74051', '74054', '74057', '74060', '74063')}
WAIT_PORTS={'52966': ('52971', '52968'), '58355': ('58361', '58358'), '58692': ('58697', '58694'), '59151': ('59162', '59156'), '63159': ('63164', '63161'), '68627': ('68647', '68639'), '71591': ('71597', '71594'), '74147': ('74152', '74149')}
FIELD_ROWS={'55382': (('55399', 13, (13,)), ('55417', 14, (14,))), '56397': (('56407', 4, (4,)),), '74086': (('74092', 4, (4,)),), '52896': (('52902', 4, (4,)),), '68552': (('68558', 4, (4,)),), '58624': (('58630', 3, (3,)),), '58982': (('58988', 3, (3,)),), '63088': (('63095', 3, (3,)),), '71528': (('71534', 3, (3,)),), '58290': (('54239', 5, (5,)), ('58296', 1, (1,)), ('58299', 2, (2,)), ('58302', 3, (3,)), ('58305', 4, (4,)), ('58308', 13, (13,)), ('58311', 14, (14,)), ('58314', 15, (15,)), ('58317', 16, (16,))), '74167': (('74179', 5, (5,)), ('74182', 1, (1,)), ('74185', 2, (2,)), ('74188', 3, (3,)), ('74191', 4, (4,)), ('74194', 13, (13,)), ('74197', 14, (14,)), ('74200', 15, (15,)), ('74203', 16, (16,))), '52981': (('52989', 5, (5,)), ('52994', 1, (1,)), ('52997', 2, (2,)), ('53001', 3, (3,)), ('53004', 4, (4,)), ('53007', 13, (13,)), ('53011', 14, (14,)), ('53016', 15, (15,)), ('53020', 16, (16,))), '68679': (('68722', 5, (5,)), ('68734', 1, (1,)), ('68740', 2, (2,)), ('68752', 3, (3,)), ('68758', 4, (4,)), ('68770', 13, (13,)), ('68774', 14, (14,)), ('68780', 15, (15,)), ('68783', 16, (16,))), '58707': (('58713', 17, (17,)), ('58716', 1, (1,)), ('58719', 2, (2,)), ('58722', 3, (3,)), ('58725', 4, (4,)), ('58729', 13, (13,)), ('58732', 14, (14,)), ('58735', 15, (15,)), ('58738', 16, (16,))), '59175': (('59188', 17, (17,)), ('59198', 1, (1,)), ('59206', 2, (2,)), ('59214', 3, (3,)), ('59219', 4, (4,)), ('59228', 13, (13,)), ('59236', 14, (14,)), ('59242', 15, (15,)), ('59248', 16, (16,))), '63176': (('63182', 17, (17,)), ('63186', 1, (1,)), ('63189', 2, (2,)), ('63192', 3, (3,)), ('63196', 4, (4,)), ('63205', 13, (13,)), ('63214', 14, (14,)), ('63217', 15, (15,)), ('63221', 16, (16,))), '71606': (('71613', 17, (17,)), ('71616', 1, (1,)), ('71619', 2, (2,)), ('71622', 3, (3,)), ('71625', 4, (4,)), ('71628', 13, (13,)), ('71631', 14, (14,)), ('71634', 15, (15,)), ('71637', 16, (16,)))}
MASK_FRAMES={1: '56252', 2: '68032', 4: '51339', 8: '57003', 16: '55658', 32: '55927', 64: '63002', 128: '66745'}
PREFIX_HEX={'55289': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465206465204D2F412064752067726F7570652048463A20', '56309': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465203C3C206465206C6120636F6E7369676E65206465206C27617474E96E7561746575722048463A20', '74219': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465203C206465206C6120636F6E7369676E65206465206C27617474E96E7561746575722048463A20', '53044': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465203E206465206C6120636F6E7369676E65206465206C27617474E96E7561746575722048463A20', '68810': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465203E3E206465206C6120636F6E7369676E65206465206C27617474E96E7561746575722048463A20', '58778': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465203C3C206465206C6120636F6E7369676E652064752064E9706861736575722048463A20', '59307': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465203C206465206C6120636F6E7369676E652064752064E9706861736575722048463A20', '63252': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465203E206465206C6120636F6E7369676E652064752064E9706861736575722048463A20', '71664': '45727265757220646520636F6D6D756E69636174696F6E2061766563206C65205356452070656E64616E74206C27656E766F6965206427756E6520636F6D6D616E6465203E3E206465206C6120636F6E7369676E652064752064E9706861736575722048463A20'}
DELTA_HEX={'56297': '4014000000000000', '74230': '3FF0000000000000', '53059': '3FF0000000000000', '68821': '3FF0000000000000', '58805': '4024000000000000', '59337': '3FF0000000000000', '63264': '3FF0000000000000', '71675': '4024000000000000'}
BORDER_UIDS=('53723','53726','53729','53732')
PREFIX_BYTES={uid:bytes.fromhex(raw)for uid,raw in PREFIX_HEX.items()}
DELTAS={uid:struct.unpack('>d',bytes.fromhex(raw))[0]for uid,raw in DELTA_HEX.items()}
LOWER_PHASE=struct.unpack('>d',bytes.fromhex('C066800000000000'))[0]
UPPER_PHASE=struct.unpack('>d',bytes.fromhex('4066800000000000'))[0]
UPPER_ATTENUATION=struct.unpack('>d',bytes.fromhex('4034000000000000'))[0]
EventDataReturn=namedtuple('EventDataReturn','event_type time control_reference old_value new_value aggregate_effective_value')
ErrorValue=namedtuple('ErrorValue','status code source_bytes')
WriterReturn=namedtuple('WriterReturn','reference_out error_out')
WriterBoundary=namedtuple('WriterBoundary','reference_in supplied_unwired_error_input returned')
WaitReturn=namedtuple('WaitReturn','timer_value')
NativeBoundaries=namedtuple('NativeBoundaries','border_values writers waits')
LocalRead=namedtuple('LocalRead','node_uid control_id saved_param_index saved_bank_uid data')
LocalAssignment=namedtuple('LocalAssignment','node_uid control_id saved_param_index saved_bank_uid data')
WriterCall=namedtuple('WriterCall','node_uid reference_constant_uid reference_literal boundary data')
WaitCall=namedtuple('WaitCall','node_uid input_terminal_uid milliseconds returned_timer')
ArithmeticStep=namedtuple('ArithmeticStep','node_uid prim_res_id input_slots output_terminal_uid value')
RangeStep=namedtuple('RangeStep','node_uid input_slots output_terminal_uid value unused_boolean_output_evaluated')
Event53716Slice=namedtuple('Event53716Slice','local_reads event_return request_vector request_any dps_any request_mask selected_frames arithmetic_steps range_steps field_updates local_assignments writer_call wait_call returned_error error_case_selector error_prefix_bytes error_text_bytes completed_sinks supplied_literal_observations')

def hex_bytes(raw):
    if type(raw)is not bytes:raise TypeError('Exact byte string required')
    return ''.join('{:02X}'.format(b)for b in raw)

def exact(value,fields):
    if type(value)is not dict or set(value)!=set(fields):raise ValueError('Exact frame53716 fields required')

def page(value):
    if type(value)is not tuple or len(value)!=26:raise TypeError('Decoded PageHF tuple26 required')
    for i,v in enumerate(value):
        if i in PAGE_FLOAT_FIELDS:
            if type(v)is not float:raise TypeError('Decoded PageHF DBL required')
        elif type(v)is not bool:raise TypeError('Decoded PageHF Boolean required')

def boolean_carrier(value):
    if type(value)is not tuple or len(value)!=29 or any(type(v)is not bool for v in value):raise TypeError('Decoded DPS tuple29Boolean required')

def dbl_carrier(value):
    if type(value)is not tuple or len(value)!=10 or any(type(v)is not float for v in value):raise TypeError('Decoded C8 tuple10DBL required')

def finite(value):
    if type(value)is not float or not math.isfinite(value)or abs(value)>NUMERIC_ABS_BOUND:raise ValueError('Finite exact DBL abs<=2**40 required')
    return value

def error(value):
    if type(value)is not ErrorValue or type(value.status)is not bool or type(value.code)is not int or not -(2**31)<=value.code<2**31 or type(value.source_bytes)is not bytes or len(value.source_bytes)>4096:raise TypeError('Decoded Boolean/I32/bounded source bytes required')

def build_request_vector(values):
    if type(values)is not tuple or len(values)!=8 or any(type(v)is not bool for v in values):raise TypeError('Eight exact source Boolean elements required')
    return values

def concatenate_error_bytes(prefix,source):
    if type(prefix)is not bytes or type(source)is not bytes or len(prefix)>4096 or len(source)>4096:raise TypeError('Bounded exact byte operands required')
    return prefix+source

def coerce_strict_interior(lower,x,upper):
    finite(lower);finite(x);finite(upper)
    if not lower<x<upper:raise ValueError('Only strict finite lower<x<upper coerce output qualified; endpoint/outside/mode/storage unresolved')
    return x

def project_event_53716(event_return,local_reads,native_boundaries,error_case_selector,literal_inputs,completed_sinks=None):
    """Direct source cases/slots/carriers under supplied typed boundaries."""
    if type(event_return)is not EventDataReturn or type(native_boundaries)is not NativeBoundaries:raise TypeError('Explicit event/native records required')
    if type(error_case_selector)is not bool:raise TypeError('Hypothetical error selector Boolean required')
    exact(local_reads,READ_UIDS);exact(native_boundaries.border_values,BORDER_UIDS)
    exact(native_boundaries.writers,WRITER_UIDS);exact(native_boundaries.waits,WAIT_UIDS);exact(literal_inputs,LITERAL_UIDS)
    page(event_return.new_value);boolean_carrier(local_reads['53769'])
    vector=build_request_vector(tuple(event_return.new_value[i]for i in REQUEST_PATHS))
    any_request=any(vector);dps_any=any(local_reads['53769']);mask=sum(1<<i for i,v in enumerate(vector)if v)
    if mask not in(0,1,2,4,8,16,32,64,128):raise ValueError('Composite mask has unqualified saved default selection')
    def read(uid,value):return LocalRead(uid,*LOCAL_IDENTITIES[uid],data=value)
    def assign(uid,value):return LocalAssignment(uid,*LOCAL_IDENTITIES[uid],data=value)
    reads=[read('53769',local_reads['53769'])];frames=[];steps=[];ranges=[];updates=[];assignments=[];literal_observations={}
    writer=None;wait=None;returned_error=None;prefix=b''
    def update(uid,values):
        rows=FIELD_ROWS[uid]
        if len(rows)!=len(values):raise ValueError('Source field-list arity mismatch')
        for row,value in zip(rows,values):updates.append((uid,row[0],row[1],row[2],value))
    def native(uid,ref_uid,data,wait_uid):
        bound=native_boundaries.writers[uid]
        if type(bound)is not WriterBoundary or type(bound.returned)is not WriterReturn:raise TypeError('Explicit selected writer returns required')
        error(bound.returned.error_out)
        call=WriterCall(uid,ref_uid,'ni.var.psp://localhost/SUPERVISION/'+('DPS'if uid=='55466'else'C8NI6703'),bound,data)
        wcall=None
        if wait_uid is not None:
            returned=native_boundaries.waits[wait_uid];milliseconds=native_boundaries.border_values['53723']
            if type(returned)is not WaitReturn or type(milliseconds)is not int or not 0<=milliseconds<2**32:raise TypeError('Supplied selected Wait/U32 input required')
            wcall=WaitCall(wait_uid,WAIT_PORTS[wait_uid][0],milliseconds,returned.timer_value)
        return call,wcall,bound.returned.error_out
    if not(any_request or dps_any):
        frames.append(('53782','53851',False));data=list(local_reads['53769']);data[13]=event_return.new_value[7];data[14]=event_return.new_value[6];dps=tuple(data)
        update('55382',(data[13],data[14]));assignments.append(assign('55371',dps))
        writer,wait,returned_error=native('55466','53857',dps,None);prefix=PREFIX_BYTES['55289']
    else:
        frames.extend((('53782','55584',True),('55624','55897'if any_request else'55756',any_request)))
        if not any_request:
            prefix=literal_inputs['55804']
            if type(prefix)is not bytes or len(prefix)>4096:raise TypeError('Explicit hypothetical decoded saved literal55804 bytes required')
            literal_observations['55804']=prefix
            returned_error=literal_inputs['55821'];error(returned_error);literal_observations['55821']=returned_error
        else:
            b=BRANCHES[mask];frames.extend((('55903',MASK_FRAMES[mask],mask),(b['sequence'],b['sequence_diag'],0)))
            c8=local_reads[b['c8read']];dbl_carrier(c8);reads.append(read(b['c8read'],c8))
            x=finite(event_return.new_value[b['page_field']]);delta=DELTAS[b['delta_uid']]
            value=x-delta if b['resid']==1051 else x+delta;finite(value)
            steps.append(ArithmeticStep(b['arith'],b['resid'],((1,delta),(2,x)),b['arith_out'],value))
            if mask<=8:
                lower=finite(literal_inputs['58402']);upper=UPPER_ATTENUATION;literal_observations['58402']=lower
            else:lower,upper=LOWER_PHASE,UPPER_PHASE
            value=coerce_strict_interior(lower,value,upper)
            ranges.append(RangeStep(b['coerce'],((2,lower),(3,value),(4,upper)),b['coerce_out'],value,False))
            pdata=list(event_return.new_value);pdata[b['page_field']]=value
            for i in REQUEST_PATHS:pdata[i]=False
            presult=tuple(pdata);update(b['pagebundle'],(value,False,False,False,False,False,False,False,False))
            cdata=list(c8);cdata[b['c8_field']]=value;cresult=tuple(cdata);update(b['c8bundle'],(value,))
            assignments.extend((assign(b['pagewrite'],presult),assign(b['c8write'],cresult)))
            writer,wait,returned_error=native(b['writer'],b['reference_uid'],cresult,b['wait']);prefix=PREFIX_BYTES[b['prefix_uid']]
    frames.append(('58205','58225'if error_case_selector else'58219',error_case_selector));text=None
    if error_case_selector:
        text=concatenate_error_bytes(prefix,returned_error.source_bytes);assignments.append(assign('58262',text))
    active={a.node_uid for a in assignments}
    if writer is not None:active.add(writer.node_uid)
    if wait is not None:active.add(wait.node_uid)
    if completed_sinks is not None:
        if type(completed_sinks)is not tuple or any(type(uid)is not str for uid in completed_sinks)or len(set(completed_sinks))!=len(completed_sinks)or any(uid not in active for uid in completed_sinks):raise ValueError('Unique caller completion subset of selected sinks required')
    return Event53716Slice(tuple(reads),event_return,vector,any_request,dps_any,mask,tuple(frames),tuple(steps),tuple(ranges),tuple(updates),tuple(assignments),writer,wait,returned_error,error_case_selector,prefix,text,completed_sinks,literal_observations)

def _json_tree(value):
    budget=[4096]
    def visit(v,depth):
        budget[0]-=1
        if budget[0]<0 or depth>10:raise ValueError('JSON node/depth bound exceeded')
        k=type(v)
        if v is None or k is bool:return
        if k is int:
            if not -(2**63)<=v<2**64:raise ValueError('JSON integer bound exceeded')
            return
        if k is float:
            if not math.isfinite(v):raise ValueError('Finite JSON numbers required')
            return
        if k is str:
            if len(v)>8192:raise ValueError('JSON string bound exceeded')
            return
        if k is list:
            if len(v)>64:raise ValueError('JSON list bound exceeded')
            for x in v:visit(x,depth+1)
            return
        if k is dict:
            if len(v)>64 or any(type(x)is not str or len(x)>256 for x in v):raise ValueError('JSON object bound exceeded')
            for x in v.values():visit(x,depth+1)
            return
        raise TypeError('Inert JSON values required')
    visit(value,0)

def _page_json(value):
    if type(value)is not list or len(value)!=26:raise TypeError('JSON PageHF26 list required')
    return tuple(value)

def _error_json(value):
    exact(value,('status','code','source_hex'))
    raw=value['source_hex']
    if type(raw)is not str or len(raw)>8192 or len(raw)%2 or any(c not in'0123456789ABCDEF'for c in raw):raise ValueError('Canonical uppercase source byte hex required')
    result=ErrorValue(value['status'],value['code'],bytes.fromhex(raw));error(result);return result

def replay_saved_sup_event_53716(payload):
    _json_tree(payload);exact(payload,('source_id','source_version','event_uid','frame_uid','local_reads','event_returns','border_inputs','unwired_inputs','reference_inputs','native_returns','error_case_selector','literal_inputs','completed_sinks'))
    if(payload['source_id'],payload['source_version'],payload['event_uid'],payload['frame_uid'])!=(SOURCE_ID,SOURCE_VERSION,EVENT_UID,FRAME_UID):raise ValueError('Exact original source/version/event/frame required')
    exact(payload['local_reads'],READ_UIDS);reads=dict(payload['local_reads']);exact(payload['literal_inputs'],LITERAL_UIDS);literals=dict(payload['literal_inputs'])
    exact(payload['event_returns'],('53735',));events=payload['event_returns']['53735'];exact(events,('53744','53749','53753','53756','53759','53762'))
    newval=_page_json(events['53762']);page(newval);event=EventDataReturn(events['53749'],events['53753'],events['53756'],events['53759'],newval,events['53744'])
    if type(reads['53769'])is not list:raise TypeError('JSON DPS29 list required')
    reads['53769']=tuple(reads['53769']);boolean_carrier(reads['53769'])
    mask=sum(1<<i for i,p in enumerate(REQUEST_PATHS)if newval[p]);active_writer=None;active_wait=None
    if mask in BRANCHES:
        b=BRANCHES[mask];uid=b['c8read']
        if type(reads[uid])is not list:raise TypeError('Selected JSON C8 carrier list required')
        reads[uid]=tuple(reads[uid]);active_writer=b['writer'];active_wait=b['wait']
    elif mask==0 and not any(reads['53769']):active_writer='55466'
    elif mask==0:
        raw=literals['55804']
        if type(raw)is not str or len(raw)>8192 or len(raw)%2 or any(c not in'0123456789ABCDEF'for c in raw):raise ValueError('Canonical supplied literal55804 byte hex required')
        literals['55804']=bytes.fromhex(raw)
        literals['55821']=_error_json(literals['55821'])
    exact(payload['border_inputs'],BORDER_UIDS)
    reference_uids=('53857',)+tuple(BRANCHES[k]['reference_uid']for k in BRANCHES);exact(payload['reference_inputs'],reference_uids)
    exact(payload['unwired_inputs'],tuple(WRITER_PORTS[u][2]for u in WRITER_UIDS));exact(payload['native_returns'],WRITER_UIDS+WAIT_UIDS)
    writers={u:payload['native_returns'][u]for u in WRITER_UIDS};waits={u:payload['native_returns'][u]for u in WAIT_UIDS}
    if active_writer is not None:
        uid=active_writer;ports=WRITER_PORTS[uid];raw=payload['native_returns'][uid];exact(raw,(ports[1],ports[3]))
        reference_uid='53857'if uid=='55466'else BRANCHES[mask]['reference_uid']
        writers[uid]=WriterBoundary(payload['reference_inputs'][reference_uid],payload['unwired_inputs'][ports[2]],WriterReturn(raw[ports[1]],_error_json(raw[ports[3]])))
    if active_wait is not None:
        raw=payload['native_returns'][active_wait];exact(raw,(WAIT_PORTS[active_wait][1],));waits[active_wait]=WaitReturn(raw[WAIT_PORTS[active_wait][1]])
    completion=payload['completed_sinks']
    if completion is not None:
        if type(completion)is not list:raise TypeError('JSON completion list or null required')
        completion=tuple(completion)
    result=project_event_53716(event,reads,NativeBoundaries(payload['border_inputs'],writers,waits),payload['error_case_selector'],literals,completion)
    def data(value):
        if type(value)is ErrorValue:return dict(status=value.status,code=value.code,source_hex=hex_bytes(value.source_bytes))
        if type(value)is bytes:return dict(bytes_hex=hex_bytes(value))
        if type(value)is tuple:return[data(v)for v in value]
        return value
    writer=None
    if result.writer_call:
        c=result.writer_call;writer=dict(node_uid=c.node_uid,reference_constant_uid=c.reference_constant_uid,reference_literal=c.reference_literal,reference_in=c.boundary.reference_in,supplied_unwired_error_input=c.boundary.supplied_unwired_error_input,data=data(c.data),supplied_returns=payload['native_returns'][c.node_uid])
    wait=None
    if result.wait_call:
        c=result.wait_call;wait=dict(node_uid=c.node_uid,input_terminal_uid=c.input_terminal_uid,milliseconds=c.milliseconds,supplied_timer_return=c.returned_timer)
    return dict(source_id=SOURCE_ID,source_version=SOURCE_VERSION,event_uid=EVENT_UID,frame_uid=FRAME_UID,saved_caption=SAVED_CAPTION,
        request_vector=list(result.request_vector),request_any=result.request_any,dps_any=result.dps_any,request_mask=result.request_mask,selected_frames=[list(v)for v in result.selected_frames],event_returns=payload['event_returns'],
        local_reads={r.node_uid:dict(control_id=r.control_id,saved_param_index=r.saved_param_index,saved_bank_uid=r.saved_bank_uid,data=data(r.data))for r in result.local_reads},
        local_assignments={a.node_uid:dict(control_id=a.control_id,saved_param_index=a.saved_param_index,saved_bank_uid=a.saved_bank_uid,data=data(a.data))for a in result.local_assignments},
        arithmetic_by_uid={s.node_uid:dict(saved_primResID=s.prim_res_id,input_slots={str(i):v for i,v in s.input_slots},output_terminal_uid=s.output_terminal_uid,value=s.value)for s in result.arithmetic_steps},
        range_by_uid={s.node_uid:dict(saved_primResID=1127,input_slots={str(i):v for i,v in s.input_slots},output_terminal_uid=s.output_terminal_uid,value=s.value,unused_boolean_output_evaluated=s.unused_boolean_output_evaluated,qualification_domain='strict_finite_lower<x<upper')for s in result.range_steps},
        field_updates=[dict(node_uid=u,terminal_uid=t,raw_flattened_field_index=i,descriptor_projection_ordinal=i,typed_position_path=list(path),value=value)for u,t,i,path,value in result.field_updates],
        writer_call=writer,wait_call=wait,returned_error=dict(status=result.returned_error.status,code=result.returned_error.code,source_hex=hex_bytes(result.returned_error.source_bytes)),
        error_case_selector=result.error_case_selector,error_prefix_hex=hex_bytes(result.error_prefix_bytes),error_text_hex=None if result.error_text_bytes is None else hex_bytes(result.error_text_bytes),
        supplied_literal_observations={u:data(v)for u,v in result.supplied_literal_observations.items()},supplied_literal_semantics='hypothetical_decoded_scalar_or_bytes_not_native_storage_decode',
        completed_sinks=None if completion is None else list(completion),completion_observation_semantics='caller_subset_in_reported_order_not_feasible_trace_or_prefix',
        selector_boundary_semantics='hypothetical_supplied_boolean_incompatible_status_pairs_do_not_prove_source_realizability',
        source_execution=False,native_execution=False,PSP_execution=False,hardware_execution=False,native_float_bitwise_equivalence=False,native_coercion_qualified=False,native_reference_decoding_qualified=False,native_error_selector_projection_qualified=False,
        native_defaults_qualified=False,unwired_native_defaults_qualified=False,native_literal_storage_decode_qualified=False,units_qualified=False,UI_permitted_values_qualified=False,event_queue_selection_qualified=False,atomic_snapshot_qualified=False,fanout_order_qualified=False,
        writer_success_gates_local_assignment=False,native_primitive_semantics_qualified=False,multi_request_mask_default_qualified=False,whole_body_qualified=False,whole_frame_equivalence=False,whole_event_equivalence=False,whole_VI_equivalence=False,
        qualification_scope='Direct source cases/request reduction/arithmetic/strict-interior-coerce/carriers/byte concat; supplied native, literal and selector boundaries')
