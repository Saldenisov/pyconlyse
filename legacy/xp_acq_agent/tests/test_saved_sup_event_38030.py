"""Fresh bounded original frame38030 tests; fixture embedded for portable packages."""
import copy
from fractions import Fraction
import json
import math
import unittest
from elyse_agent import saved_sup_event_38030 as m

FIXTURE_JSON = '{"border_inputs":{"38037":123,"38040":{"unused_registration_ref":true},"38043":{"unused_timeout":true},"38046":{"unused_registration_ref":true}},"completed_sinks":["44959","38326"],"error_case_selector":true,"event_returns":{"38049":{"38051":{"unwired_aggregate_effective":true},"38054":{"unused_type":true},"38058":{"unused_time":true},"38062":{"unused_control_reference":true},"38070":{"old_value_independent":true},"38074":[false,false,false,[0.0,1.0,2.0,3.0,4.0,5.0,6.0],14.0,15.0,false,false,false,false,false,false,false,false,false,false,false,false,false,false,true,31.0,32.0]}},"event_uid":"5909","frame_uid":"38030","local_reads":{"11796":[false,false,false,[20.0,21.0,22.0,23.0,24.0,25.0,26.0],105.0,106.0,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,122.0,123.0],"38095":[false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false],"38705":[201.0,202.0,203.0,204.0,205.0,206.0,207.0,208.0,209.0,210.0],"43037":[false,false,false,[20.0,21.0,22.0,23.0,24.0,25.0,26.0],106.0,107.0,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,123.0,124.0],"43064":[202.0,203.0,204.0,205.0,206.0,207.0,208.0,209.0,210.0,211.0],"45088":[false,false,false,[20.0,21.0,22.0,23.0,24.0,25.0,26.0],108.0,109.0,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,125.0,126.0],"45134":[204.0,205.0,206.0,207.0,208.0,209.0,210.0,211.0,212.0,213.0],"48871":[false,false,false,[20.0,21.0,22.0,23.0,24.0,25.0,26.0],112.0,113.0,false,true,false,false,false,false,false,false,false,false,false,false,false,false,false,129.0,130.0],"48897":[208.0,209.0,210.0,211.0,212.0,213.0,214.0,215.0,216.0,217.0]},"native_returns":{"36455":{"36465":{"unused_reference_return":"36455"},"36621":{"code":-77,"source_hex":"00505350FF","status":true}},"38229":{"38237":{"unused_reference_return":"38229"},"38243":{"code":-77,"source_hex":"00505350FF","status":true}},"38508":{"38518":{"unused_timer_return":"38508"}},"42992":{"42997":{"unused_reference_return":"42992"},"43003":{"code":-77,"source_hex":"00505350FF","status":true}},"44982":{"44994":{"unused_reference_return":"44982"},"45013":{"code":-77,"source_hex":"00505350FF","status":true}},"48837":{"48842":{"unused_reference_return":"48837"},"48848":{"code":-77,"source_hex":"00505350FF","status":true}},"56723":{"56725":{"unused_timer_return":"56723"}},"57473":{"57475":{"unused_timer_return":"57473"}},"61892":{"61894":{"unused_timer_return":"61892"}},"62593":{"62595":{"unused_timer_return":"62593"}}},"reference_inputs":{"36087":{"decoded_reference_boundary":"36087"},"38160":{"decoded_reference_boundary":"38160"},"43093":{"decoded_reference_boundary":"43093"},"45220":{"decoded_reference_boundary":"45220"},"48937":{"decoded_reference_boundary":"48937"}},"source_id":"APP-17","source_version":"D3356F86853E718BB80F5F874620E201CA635400025D35DF6DBC2629C14874A9","unwired_inputs":{"36600":{"effective_native_default_supplied":"36455"},"38240":{"effective_native_default_supplied":"38229"},"43000":{"effective_native_default_supplied":"42992"},"45004":{"effective_native_default_supplied":"44982"},"48845":{"effective_native_default_supplied":"48837"}}}'

def fixture():return json.loads(FIXTURE_JSON)

def selected(mask,status=True,selector=True):
    p=fixture();v=p['event_returns']['38049']['38074']
    for i,path in enumerate(m.REQUEST_PATHS):v[path]=bool(mask&(1<<i))
    p['error_case_selector']=selector;p['completed_sinks']=None
    for uid in m.WRITER_UIDS:p['native_returns'][uid][m.WRITER_PORTS[uid][3]]['status']=status
    return p

def pure(p):
    reads=dict(p['local_reads']);reads['38095']=tuple(reads['38095'])
    for b in m.BRANCHES.values():
        v=reads[b[3]];v=list(v);v[3]=tuple(v[3]);reads[b[3]]=tuple(v);reads[b[6]]=tuple(reads[b[6]])
    e=p['event_returns']['38049'];v=list(e['38074']);v[3]=tuple(v[3]);v=tuple(v)
    event=m.EventDataReturn(e['38054'],e['38058'],e['38062'],e['38070'],v,e['38051'])
    writers={}
    for uid,ref in zip(m.WRITER_UIDS,('38160','36087','43093','45220','48937')):
        ports=m.WRITER_PORTS[uid];raw=p['native_returns'][uid];err=raw[ports[3]]
        writers[uid]=m.WriterBoundary(p['reference_inputs'][ref],p['unwired_inputs'][ports[2]],m.WriterReturn(raw[ports[1]],m.ErrorValue(err['status'],err['code'],bytes.fromhex(err['source_hex']))))
    waits={uid:m.WaitReturn(p['native_returns'][uid][m.WAIT_PORTS[uid][1]])for uid in m.WAIT_UIDS}
    native=m.NativeBoundaries(dict(p['border_inputs']),writers,waits)
    completion=None if p['completed_sinks']is None else tuple(p['completed_sinks'])
    return event,reads,native,p['error_case_selector'],completion

class Poison(object):
    def __getattr__(self,name):raise AssertionError('Unselected/opaque value touched')
    def __bool__(self):raise AssertionError('Opaque truth tested')
    def __iter__(self):raise AssertionError('Opaque iterated')
    def __len__(self):raise AssertionError('Opaque measured')
    def __str__(self):raise AssertionError('Opaque stringified')

class TestSavedSupEvent38030(unittest.TestCase):
    def test_fraction_numeric_branches_and_distinct_read_epochs(self):
        for mask in(1,2,4,8):
            for x in(-float(2**40),-13.25,-0.1,-0.0,0.1,2.126,8.98,31.0,float(2**40)):
                p=selected(mask);target=m.BRANCHES[mask][15];p['event_returns']['38049']['38074'][target]=x
                a=m.project_event_38030(*pure(p));expected=float(Fraction.from_float(x)+(-1 if mask in(1,4)else 1)*Fraction.from_float(m.DELTA))
                self.assertEqual(a.arithmetic_steps[0].value,expected)
                self.assertEqual(a.arithmetic_steps[0].input_slots,((1,m.DELTA),(2,x)))
                self.assertNotEqual(a.local_reads[1].data[target],x)
                self.assertEqual(m.replay_saved_sup_event_38030(p)['arithmetic_by_uid'][m.BRANCHES[mask][0]]['value'],expected)
    def test_duplicate_raw13_and_carrier_untouched_identity(self):
        for mask in(1,2,4,8):
            args=pure(selected(mask));a=m.project_event_38030(*args);b=m.BRANCHES[mask];before=args[1][b[3]];after=a.local_assignments[0].data
            changed={b[15],6,19,20};changed.update(())if mask==4 else changed.add(7)
            for i,v in enumerate(before):
                if i not in changed:self.assertIs(after[i],v)
            self.assertIs(after[3],before[3])
            cbefore=args[1][b[6]];cafter=a.local_assignments[1].data
            for i,v in enumerate(cbefore):
                if i!=b[16]:self.assertIs(cafter[i],v)
            fields=[r[1]for r in a.field_updates if r[0]==b[5]]
            self.assertEqual(fields[1:], [13,13,26,27]if mask==4 else[13,14,26,27])
            if mask==4:
                self.assertIs(after[7],before[7]);self.assertTrue(after[7]);output=m.replay_saved_sup_event_38030(selected(mask));rows=[r for r in output['field_updates']if r['node_uid']=='45095'and r['raw_flattened_field_index']==13];self.assertEqual([r['terminal_uid']for r in rows],['8796','63276'])
    def test_fresh_dps_branch_and_no_request_noop(self):
        for start in(False,True):
            for stop in(False,True):
                p=selected(0);v=p['event_returns']['38049']['38074'];v[9]=start;v[8]=stop;a=m.project_event_38030(*pure(p))
                self.assertEqual(a.field_updates[0][1],None);self.assertEqual(a.field_updates[0][2],(0,));
                output=m.replay_saved_sup_event_38030(p);row=output['field_updates'][0];self.assertIsNone(row['raw_flattened_field_index']);self.assertEqual(row['descriptor_projection_ordinal'],0);self.assertEqual(row['typed_position_path'],[0]);self.assertEqual(row['terminal_uid'],'38218');
                self.assertEqual(a.local_assignments[0].data[:2],(start,stop));self.assertEqual(a.writer_call.node_uid,'38229');self.assertEqual(a.wait_call.node_uid,'62593')
        p=selected(0);p['local_reads']['38095'][22]=True;p['error_case_selector']=False;a=m.project_event_38030(*pure(p))
        self.assertFalse(a.local_assignments);self.assertIsNone(a.writer_call);self.assertIsNone(a.wait_call);self.assertEqual(a.selected_frames[:2],(('38117','38451',True),('39025','43139',False)))
    def test_hypothetical_error_selector_and_raw_byte_concat(self):
        for mask in(0,1,2,4,8):
            for status in(False,True):
                for selector in(False,True):
                    a=m.project_event_38030(*pure(selected(mask,status,selector)))
                    self.assertEqual(a.returned_error.status,status)
                    if selector:self.assertEqual(a.error_text_bytes,a.error_prefix_bytes+b'\x00PSP\xff');self.assertEqual(a.local_assignments[-1].node_uid,'38326')
                    else:self.assertIsNone(a.error_text_bytes)
                    self.assertTrue(a.local_assignments) # faulted writer never gates assignment
    def test_active_only_reads_and_native_opaque_nonaccess(self):
        for mask in(0,1,2,4,8):
            args=list(pure(selected(mask)));event,reads,native,selector,completion=args;poison=Poison()
            active_reads={'38095'};writer='38229';wait='62593'
            if mask:active_reads.update((m.BRANCHES[mask][3],m.BRANCHES[mask][6]));writer=m.BRANCHES[mask][9];wait=m.BRANCHES[mask][11]
            for uid in m.READ_UIDS:
                if uid not in active_reads:reads[uid]=poison
            for uid in m.WRITER_UIDS:
                if uid!=writer:native.writers[uid]=poison
            for uid in m.WAIT_UIDS:
                if uid!=wait:native.waits[uid]=poison
            native.border_values['38040']=poison;native.border_values['38043']=poison;native.border_values['38046']=poison
            boundary=native.writers[writer];native.writers[writer]=m.WriterBoundary(poison,poison,m.WriterReturn(poison,boundary.returned.error_out));native.waits[wait]=m.WaitReturn(poison)
            args[0]=m.EventDataReturn(poison,poison,poison,poison,event.new_value,poison);a=m.project_event_38030(*args)
            self.assertIs(a.writer_call.boundary.reference_in,poison);self.assertIs(a.writer_call.boundary.returned.reference_out,poison);self.assertIs(a.wait_call.returned_timer,poison);self.assertIs(a.event_return.old_value,poison)
        args=list(pure(selected(0)));reads=args[1];dps=list(reads['38095']);dps[0]=True;reads['38095']=tuple(dps);native=args[2]
        for uid in m.WRITER_UIDS:native.writers[uid]=Poison()
        for uid in m.WAIT_UIDS:native.waits[uid]=Poison()
        native.border_values['38037']=Poison();a=m.project_event_38030(*args);self.assertIsNone(a.writer_call)
    def test_completion_observations_are_selected_subsets_not_trace(self):
        for mask in(0,1,2,4,8):
            args=list(pure(selected(mask)));a=m.project_event_38030(*args);active=[x.node_uid for x in a.local_assignments]+[a.writer_call.node_uid,a.wait_call.node_uid]
            for bits in range(1<<len(active)):
                completion=tuple(u for i,u in enumerate(active)if bits&(1<<i));args[-1]=completion;self.assertEqual(m.project_event_38030(*args).completed_sinks,completion)
            args[-1]=tuple(reversed(active));self.assertEqual(m.project_event_38030(*args).completed_sinks,tuple(reversed(active)))
            for bad in((active[0],active[0]),('999999',),[active[0]],(False,)):
                args[-1]=bad
                with self.assertRaises((TypeError,ValueError)):m.project_event_38030(*args)
    def test_composite_mask_and_invalid_numeric_domains_refused(self):
        for mask in(3,5,6,7,9,10,11,12,13,14,15):
            with self.assertRaises(ValueError):m.replay_saved_sup_event_38030(selected(mask))
        for value in(0,True,float('nan'),float('inf'),float(2**41)):
            args=list(pure(selected(1)));v=list(args[0].new_value);v[4]=value;args[0]=args[0]._replace(new_value=tuple(v))
            with self.assertRaises((TypeError,ValueError)):m.project_event_38030(*args)
    def test_strict_source_and_json_payload_guards(self):
        for key,value in(('source_id','APP-00'),('source_version','0'*64),('event_uid','43'),('frame_uid','38031'),('error_case_selector',1)):
            p=fixture();p[key]=value
            with self.assertRaises((ValueError,TypeError)):m.replay_saved_sup_event_38030(p)
        for mutate in(lambda p:p.update(extra=0),lambda p:p['local_reads'].pop('11796'),lambda p:p['border_inputs'].update({'38037':True}),lambda p:p['native_returns']['44982']['45013'].update(source_hex='ff'),lambda p:p['event_returns']['38049']['38074'].__setitem__(6,1),lambda p:p.update(completed_sinks=['38229'])):
            p=fixture();mutate(p)
            with self.assertRaises((ValueError,TypeError)):m.replay_saved_sup_event_38030(p)
    def test_scalar_build_and_concat_fail_closed(self):
        for v in([True]*4,(True,)*3,(1,False,False,False),Poison()):
            with self.assertRaises(TypeError):m.build_request_vector(v)
        for a,b in(('a',b'b'),(b'a','b'),(Poison(),b''),(b'x'*4097,b'')):
            with self.assertRaises(TypeError):m.concatenate_error_bytes(a,b)
        self.assertEqual(m.concatenate_error_bytes(b'\x00\xe9',b'\xff'),b'\x00\xe9\xff')
    def test_json_execution_and_native_gates_remain_false(self):
        out=m.replay_saved_sup_event_38030(fixture())
        for k in('source_execution','native_execution','PSP_execution','hardware_execution','native_float_bitwise_equivalence','native_error_selector_projection_qualified','native_defaults_qualified','whole_body_qualified','whole_frame_equivalence','whole_event_equivalence','whole_VI_equivalence'):self.assertIs(out[k],False)
        self.assertIn('hypothetical',out['selector_boundary_semantics']);self.assertIn('not_feasible_trace',out['completion_observation_semantics'])

if __name__=='__main__':unittest.main()
